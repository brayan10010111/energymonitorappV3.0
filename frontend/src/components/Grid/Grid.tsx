import React from 'react';
import type { ReactNode } from 'react';
import './Grid.css'


interface GridProps {
  children?: ReactNode;
}

const Grid: React.FC<GridProps> = ({ children }) => {
    return (
        <div className='div-responsive'>{children}</div>
    );
}

export default Grid;

