// src/components/Layout.tsx
import Sidebar from '../../components/Sidebar/Sidebar';
import { Outlet } from 'react-router-dom';
// import { useState } from 'react';

/**
 * Props del layout compartido.
 * `collapsed` controla el ancho del sidebar y del contenedor principal.
 */
type LayoutProps = {
  collapsed: boolean;
  setCollapsed: (value: boolean) => void;
};

/**
 * Layout base de la app.
 *
 * - Renderiza `Sidebar`.
 * - Renderiza `Outlet` para las rutas hijas.
 * - Expone `{ collapsed, setCollapsed }` vía `Outlet context`.
 */
const Layout: React.FC<LayoutProps> = ({ collapsed, setCollapsed }) => {
  return (
    <div className="app-container">
      <Sidebar collapsed={collapsed} setCollapsed={setCollapsed} />
      <div className={`main-content ${collapsed ? 'collapsed' : ''}`}>
        <Outlet context={{ collapsed, setCollapsed }} />
      </div>
    </div>
  );
};

export default Layout;

