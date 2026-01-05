import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

/**
 * Punto de entrada de React (Vite).
 *
 * Monta la aplicación en el nodo `#root` y activa `StrictMode` para
 * ayudar a detectar efectos secundarios durante desarrollo.
 */
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

