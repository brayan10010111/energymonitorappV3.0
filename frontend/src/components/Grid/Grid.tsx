import React from 'react';
import type { ReactNode } from 'react';
import './Grid.css'

/** Props del contenedor Grid. */
interface GridProps {
  children?: ReactNode;
}

/**
 * Contenedor responsivo para layouts tipo grilla.
 *
 * Se usa para ubicar varios componentes (gráficas/cards) adaptándose al ancho.
 */
const Grid: React.FC<GridProps> = ({ children }) => {
    return (
        <div className='div-responsive'>{children}</div>
    );
}

export default Grid;

