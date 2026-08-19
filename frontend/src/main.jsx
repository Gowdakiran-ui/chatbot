import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// Self-hosted (not a CDN) so the app never depends on network access for its
// own typography — a real product concern, not just an offline nicety.
import '@fontsource/orbitron/700.css'
import '@fontsource/orbitron/900.css'
import '@fontsource/rajdhani/500.css'
import '@fontsource/rajdhani/600.css'
import '@fontsource/rajdhani/700.css'
import '@fontsource/share-tech-mono/400.css'
import './index.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
