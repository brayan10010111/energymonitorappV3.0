import React from "react";
import type { Equipo } from "../../db/db";
import "./EquiposModal.css";

/**
 * Props del modal de selección de equipos/medidores.
 *
 * El estado de selección se mantiene en el padre y se modifica con callbacks.
 */
interface EquiposModalProps {
  equipos: Equipo[];
  medidoresSeleccionados: string[];
  toggleMedidor: (nombre: string) => void;
  toggleTodos: () => void;
  onClose: () => void;
}

/**
 * Modal para seleccionar uno o varios equipos.
 *
 * - Permite seleccionar por fila o checkbox.
 * - Permite seleccionar/deseleccionar todos.
 */
const EquiposModal: React.FC<EquiposModalProps> = ({
  equipos,
  medidoresSeleccionados,
  toggleMedidor,
  toggleTodos,
  onClose,
}) => {
  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <div className="equipos-header">
          {/* Botón de cerrar */}
          <button onClick={onClose} className="btn-cerrar">
            ✕
          </button>
          <h3 className="textos titulo-h3">Equipos / Medidores</h3>


          <div className="seleccion-info">
            <span className="contador textos">
              {medidoresSeleccionados.length} de {equipos.length} seleccionados
            </span>
            {equipos.length > 0 && (
              <button onClick={toggleTodos} className="btn-todos textos">
                {medidoresSeleccionados.length === equipos.length
                  ? "Deseleccionar"
                  : "Seleccionar"}{" "}
                todos
              </button>
            )}
          </div>
        </div>

        <div className="tabla-wrapper">
          <table className="tabla-equipos">
            <thead>
              <tr>
                <th style={{ width: "50px" }}></th>
                <th>Nombre</th>
                <th>Modelo</th>
                <th>IP</th>
                <th>ID Modbus</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {equipos.length === 0 ? (
    <tr>
      <td colSpan={5} style={{ textAlign: "center", padding: "2rem", color: "#888" }}>
        Cargando equipos...
      </td>
    </tr>
  ) : (
    equipos.map((equipo) => (
      <tr
        key={equipo.id}
        className={medidoresSeleccionados.includes(equipo.nombre) ? "seleccionado" : ""}
        onClick={() => toggleMedidor(equipo.nombre)} // Selección al hacer clic en la fila
        style={{ cursor: "pointer" }}
      >
        <td className="celda-check">
          <input
            type="checkbox"
            checked={medidoresSeleccionados.includes(equipo.nombre)}
            onClick={(e) => e.stopPropagation()} // Evita que el clic en el checkbox seleccione la fila
            onChange={() => toggleMedidor(equipo.nombre)}
          />
        </td>
        <td><strong>{equipo.nombre}</strong></td>
        <td>{equipo.modelo}</td>
        <td>{equipo.ip}</td>
        <td>
          <span className={`estado ${equipo.estado?.toLowerCase()}`}>
            {equipo.estado}
          </span>
        </td>
        <td>{equipo.id_modbus}</td>
      </tr>
    ))
  )}

            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default EquiposModal;
