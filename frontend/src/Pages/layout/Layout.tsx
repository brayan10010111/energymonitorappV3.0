// src/components/Layout.tsx
import Sidebar from '../../components/Sidebar/Sidebar';
import { Outlet } from 'react-router-dom';
// import { useState } from 'react';

type LayoutProps = {
  collapsed: boolean;
  setCollapsed: (value: boolean) => void;
};



const Layout: React.FC<LayoutProps> = ({ collapsed, setCollapsed }) => {
  return (
    <div className="app-container">
      <Sidebar collapsed={collapsed} setCollapsed={setCollapsed} />
      <div className={`main-content ${collapsed ? 'collapsed' : ''}`}>
        <Outlet />
      </div>
    </div>
  );
};

export default Layout;

