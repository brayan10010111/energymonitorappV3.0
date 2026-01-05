// import { useState } from 'react'
// import reactLogo from './assets/react.svg'
// import viteLogo from '/vite.svg'

import './App.css'

import { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Equipos from './Pages/equipos/Equipos';
import Dashboard from './Pages/dashboard/Dashboard';
import Layout from './Pages/layout/Layout';
import Informes from './Pages/Informes/Informes';
import Predictivo from './Pages/Predictivo/Predictivo';

/**
 * Componente raíz de la app.
 *
 * Responsabilidades:
 * - Configurar el Router.
 * - Envolver las rutas en `Layout`.
 * - Mantener el estado `collapsed` del sidebar para compartirlo entre vistas.
 */
function App() {
const [collapsed, setCollapsed] = useState(false);

  return (
    <Router>
      <Routes>
        {/* Ruta padre que envuelve todo con el Layout */}
        <Route
          element={<Layout collapsed={collapsed} setCollapsed={setCollapsed} />}
        >
          {/* Ruta por defecto: redirige o muestra el dashboard */}
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard collapsed={collapsed} />} />
          <Route path="equipos" element={<Equipos />} />
          <Route path="informes" element={<Informes />} />
          <Route path="predictivo" element={<Predictivo />} />
          {/* Opcional: ruta 404 */}
          <Route path="*" element={<div>Página no encontrada</div>} />
        </Route>
      </Routes>
    </Router>
  );
}



export default App;



