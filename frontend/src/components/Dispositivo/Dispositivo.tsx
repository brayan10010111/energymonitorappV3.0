import './Dispositivo.css'
import React from 'react';

/**
 * Forma esperada del equipo a mostrar en la tabla.
 * (Este tipo está duplicado respecto a `db.tsx`; aquí se usa solo para UI.)
 */
interface Equipo {
  id: number;
  nombre: string;
  modelo: string;
  ip: string;
  id_modbus: number;
  estado: string;
}

/**
 * Props de la fila `Dispositivo`.
 * - `seleccionado` controla el checkbox.
 * - `onToggle` notifica al padre para agregar/quitar el id.
 */
interface DispositivoProps {
  equipo: Equipo;
  seleccionado: boolean;
  onToggle: (id: number) => void;
}

/**
 * Fila de tabla para un equipo.
 *
 * Renderiza valores y un checkbox de selección.
 */
const Dispositivo: React.FC<DispositivoProps> = ({ equipo, seleccionado, onToggle }) => {
  return (
    <tr className="filas">
      <td>
        <input
          type="checkbox"
          checked={seleccionado}
          onChange={() => onToggle(equipo.id)}
        />
      </td>
      <td>{equipo.nombre}</td>
      <td>{equipo.modelo}</td>
      <td>{equipo.ip}</td>
      <td>{equipo.id_modbus}</td>
      <td className={equipo.estado === "Online" ? "estado-online" : "estado-offline"}>
        {equipo.estado}
      </td>

      <td></td>
    </tr>
  );
};

export default Dispositivo;