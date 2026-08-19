// Piece 4 visual QA — real rendered screenshots via Playwright, not DOM
// state. Grounded-answer screenshots use the real live backend (2 calls,
// one per mode); refusal/truncated/error screenshots intercept the /chat
// network call with response bodies matching the backend's actual literal
// text exactly (real refusal copy from serving/floor.py, real
// TRUNCATION_NOTICE/disclaimer text from serving/app.py) so they're
// visually faithful without needing to win a live non-determinism lottery.
import { chromium } from 'playwright';
import { mkdirSync } from 'fs';

const OUT_DIR = '.qa-screenshots';
mkdirSync(OUT_DIR, { recursive: true });

const BASE_URL = 'http://localhost:5173';

const CHANAKYA_REFUSAL_TEXT =
  'I do not have a teaching among my retrieved texts that speaks directly to this. I would rather tell you ' +
  'plainly that I lack a grounded source here than offer counsel I cannot trace back to the Arthashastra or ' +
  'Chanakya Niti.';

const CRISIS_REFUSAL_TEXT =
  "I don't have a documented precedent among the retrieved crisis cases that matches this situation closely " +
  "enough to advise from. Rather than generalize past what's grounded, I'm flagging this for human review. " +
  'This is not legal advice. For regulatory or legal questions, the client should consult qualified counsel.';

const TRUNCATION_NOTICE = '\n\n[Response truncated — ask a follow-up for more detail.]';
const DISCLAIMER = 'This is not legal advice. For regulatory or legal questions, the client should consult qualified counsel.';

function sse(events) {
  return events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join('');
}

function refusalBody(mode) {
  const text = mode === 'crisis' ? CRISIS_REFUSAL_TEXT : CHANAKYA_REFUSAL_TEXT;
  return sse([
    { type: 'token', text },
    { type: 'final', mode, refused: true, top_score: 0.4, top_dense_score: 0.4, cited_chunk_ids: [], conversation_id: 'qa' },
  ]);
}

function groundedAnswerText(mode) {
  if (mode === 'crisis') {
    return (
      'The closest precedent is the **TalkTalk (2015)** breach, which mirrors your situation closely: a cyberattack ' +
      'exposing customer data, public anger, and journalists demanding comment.\n\n' +
      "**What went wrong**\n\nTalkTalk's then-CEO Dido Harding gave live interviews before the technical facts " +
      'were confirmed — a decision still cited today as a textbook example of what not to do in a breach response. ' +
      'The story became about the company\'s security negligence rather than the attacker\'s crime.\n\n' +
      '**What this means for you**\n\nDo not put a spokesperson in front of a journalist until they have a firm, ' +
      'accurate grip on what data moved and how many customers are affected.'
    );
  }
  return (
    'As I have written in the Arthashastra, a king who trusts too quickly invites his own ruin. Your situation ' +
    'calls for the same discipline I once showed with Chandragupta.\n\n' +
    '**First, secure what remains.** Do not react in anger — protect your assets, your remaining clients, and ' +
    'your reputation before anything else.\n\n' +
    '**Second, do not attack the capital directly.** I besieged the outlying cities before Pataliputra. In your ' +
    "world, this means strengthening your weaker relationships before confronting the betrayal head-on."
  );
}

function truncatedBody(mode) {
  const disclaimer = mode === 'crisis' ? `\n\n${DISCLAIMER}` : '';
  const text = groundedAnswerText(mode) + TRUNCATION_NOTICE + disclaimer;
  return sse([
    { type: 'token', text },
    {
      type: 'final',
      mode,
      refused: false,
      top_score: 0.82,
      top_dense_score: 0.79,
      cited_chunk_ids: mode === 'crisis' ? ['talktalk_2015_summary', 'talktalk_2015_went_wrong'] : ['arthashastra_book_i_chapter_xi_003'],
      conversation_id: 'qa',
    },
  ]);
}

function errorBody() {
  return sse([
    { type: 'token', text: 'Here is the beginning of a grounded answer before the connection dropped mid-' },
    { type: 'error', message: 'Connection lost while streaming the response.' },
  ]);
}

const VIEWPORTS = {
  desktop: { width: 1280, height: 800 },
  mobile: { width: 390, height: 844 },
};

async function typeAndSend(page, text) {
  await page.locator('textarea').fill(text);
  await page.locator('.message-input-send').click();
}

async function waitForDone(page, { timeoutMs = 60000 } = {}) {
  await page.locator('.status-done, .message-bubble-refusal, .message-error-note').last().waitFor({ timeout: timeoutMs });
  // let the stream-cursor/animation settle and layout finish
  await page.waitForTimeout(400);
}

async function shoot(page, viewportName, name) {
  await page.setViewportSize(VIEWPORTS[viewportName]);
  await page.waitForTimeout(150);
  // Content reflows taller at a narrower width, so the scroll position
  // inherited from the previous (desktop) viewport doesn't necessarily keep
  // the latest message in view anymore — re-scroll explicitly after every
  // resize rather than trusting the old position. Caught by actually
  // looking at the first render of these screenshots (task.md's mandate),
  // not assumed correct.
  await page.evaluate(() => {
    const history = document.querySelector('.chat-history');
    if (history) history.scrollTop = history.scrollHeight;
  });
  await page.waitForTimeout(100);
  await page.screenshot({ path: `${OUT_DIR}/${viewportName}_${name}.png`, fullPage: false });
  console.log(`captured ${viewportName}_${name}.png`);
}

async function switchMode(page, mode) {
  const target = mode === 'crisis' ? 1 : 0;
  await page.locator('[role="radio"]').nth(target).click();
  await page.waitForTimeout(500); // let the glitch transition finish
}

async function main() {
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: VIEWPORTS.desktop });
  const page = await context.newPage();

  page.on('console', (msg) => {
    if (msg.type() === 'error') console.log('  [console error]', msg.text());
  });

  await page.goto(BASE_URL, { waitUntil: 'networkidle' });

  // --- Landing state (Piece 1: auth bypass skips token entry) ---
  await shoot(page, 'desktop', '01_landing');
  await shoot(page, 'mobile', '01_landing');
  await page.setViewportSize(VIEWPORTS.desktop);

  // --- Grounded answers: REAL live backend, one per mode ---
  await typeAndSend(page, 'my business partner betrayed me and joined our biggest competitor, what would chanakya do');
  await waitForDone(page, { timeoutMs: 90000 });
  await shoot(page, 'desktop', '02_grounded_chanakya');
  await shoot(page, 'mobile', '02_grounded_chanakya');
  await page.setViewportSize(VIEWPORTS.desktop);

  await switchMode(page, 'crisis');
  await typeAndSend(page, 'Nirav Modi Punjab National Bank fraud case summary');
  await waitForDone(page, { timeoutMs: 90000 });
  await shoot(page, 'desktop', '03_grounded_crisis');
  await shoot(page, 'mobile', '03_grounded_crisis');
  await page.setViewportSize(VIEWPORTS.desktop);

  // --- Synthetic states: network-intercepted, real text, deterministic ---
  let currentBodyFn = null;
  await page.route('**/chat', async (route) => {
    const body = currentBodyFn();
    await route.fulfill({ status: 200, contentType: 'text/event-stream', body });
  });

  const scenarios = [
    { name: 'refusal', label: '04_refusal', bodyFn: (mode) => refusalBody(mode) },
    { name: 'truncated', label: '05_truncated', bodyFn: (mode) => truncatedBody(mode) },
    { name: 'error', label: '06_error', bodyFn: () => errorBody() },
  ];

  for (const mode of ['chanakya', 'crisis']) {
    const activeIsCrisis = await page.locator('.mode-toggle-crisis').getAttribute('aria-checked');
    if (mode === 'crisis' && activeIsCrisis !== 'true') await switchMode(page, 'crisis');
    if (mode === 'chanakya' && activeIsCrisis === 'true') await switchMode(page, 'chanakya');

    for (const scenario of scenarios) {
      currentBodyFn = () => scenario.bodyFn(mode);
      await typeAndSend(page, `[QA] triggering the ${scenario.name} state in ${mode} mode`);
      await waitForDone(page, { timeoutMs: 15000 });
      await shoot(page, 'desktop', `${scenario.label}_${mode}`);
      await shoot(page, 'mobile', `${scenario.label}_${mode}`);
      await page.setViewportSize(VIEWPORTS.desktop);
    }
  }

  await browser.close();
  console.log('done');
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
