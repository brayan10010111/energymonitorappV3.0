// Sidebar.tsx
import {FaChartBar, FaFileAlt, FaCog } from "react-icons/fa";
import { MdDevices } from "react-icons/md";
import React, { useState, useEffect } from 'react';
import "./Sidebar.css";
import { Link } from 'react-router-dom';

/**
 * Props del Sidebar.
 * - `collapsed`: indica si está colapsado visualmente.
 * - `setCollapsed`: actualiza el estado compartido en `App/Layout`.
 */
type SidebarProps = {
  collapsed: boolean;
  setCollapsed: (value: boolean) => void;
};

/**
 * Sidebar de navegación.
 *
 * Comportamiento:
 * - Responsive: si el ancho < BREAKPOINT, fuerza colapsado.
 * - Toggle manual: en pantallas grandes permite alternar colapsado/expandido.
 */
const Sidebar: React.FC<SidebarProps> = ({ collapsed, setCollapsed }) => {

  const BREAKPOINT = 600;
  const [isManuallyToggled, setIsManuallyToggled] = useState(false);
  useEffect(() => {
    /**
     * Maneja resize: colapsa automáticamente en pantallas pequeñas.
     * En pantallas grandes, respeta el toggle manual.
     */
    const handleResize = () => {
      if (window.innerWidth < BREAKPOINT) {
        setCollapsed(true);
      } else {
        setCollapsed(isManuallyToggled);
      }
    };
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, [isManuallyToggled]); // Se vuelve a ejecutar si el estado del toggle manual cambia

  /** Alterna el estado manual de colapso (solo aplica a pantallas >= BREAKPOINT). */
  const handleToggleSidebar = () => {
    const newToggleState = !isManuallyToggled;
    setIsManuallyToggled(newToggleState);
    if (window.innerWidth >= BREAKPOINT) {
      setCollapsed(newToggleState);
    }
  };

  return (
   <div className={`sidebar ${collapsed ? "collapsed" : ""}`}>
      <div className="sidebar-header">
        {collapsed && (
          <span className="toggle-icon " onClick={handleToggleSidebar}>
            ☰
          </span>
        )}
        {!collapsed && (
          <h2 className="header-title" onClick={handleToggleSidebar}>
            Menú
          </h2>
        )}
      </div>

      <ul>
        <li><Link to="/equipos" className="sidebar-link"> {collapsed ? <MdDevices className='iconoscol' /> : <> <MdDevices className='iconos' />  Equipos </>}</Link></li>
        <li><Link to="/dashboard" className="sidebar-link">{collapsed ? <FaChartBar className='iconoscol'/> : <> <FaChartBar  className='iconos'/>  Dashboard </>}</Link></li>
        <li><Link to="/informes" className="sidebar-link">{collapsed ? <FaFileAlt className='iconoscol'/> : <> <FaFileAlt  className='iconos'/>  Informes </>}</Link></li>
        <li><Link to="/predictivo" className="sidebar-link">{collapsed ? <FaCog className='iconoscol'/> : <> <FaCog  className='iconos' />  Predictivo </>}</Link></li>
      </ul>
    </div>
  );

}

export default Sidebar;
