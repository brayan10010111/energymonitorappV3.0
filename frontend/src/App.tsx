// import { useState } from 'react'
// import reactLogo from './assets/react.svg'
// import viteLogo from '/vite.svg'

import './App.css'

import { useState } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Equipos from './Pages/equipos/Equipos';
import Dashboard from './Pages/dashboard/Dashboard';
import Layout from './Pages/layout/Layout';

function App() {
const [collapsed, setCollapsed] = useState(false);

  return (
    <Router>
      <Routes>
        <Route
          path="/"
          element={<Layout collapsed={collapsed} setCollapsed={setCollapsed} />}
        >

          <Route path="equipos" element={<Equipos />} />
           <Route path="dashboard" element={<Dashboard collapsed={collapsed} />} />

          {/* <Route path="informes" element={<Informes />} />
          <Route path="configuracion" element={<Configuracion />} /> */}
        </Route>
      </Routes>
    </Router>
  );
}



export default App;



