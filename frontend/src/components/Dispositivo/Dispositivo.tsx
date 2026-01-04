import './Dispositivo.css'
import React from 'react';
interface Equipo {
  id: number;
  nombre: string;
  modelo: string;
  ip: string;
  id_modbus: number;
  estado: string;
}

interface DispositivoProps {
  equipo: Equipo;
  seleccionado: boolean;
  onToggle: (id: number) => void;
}

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