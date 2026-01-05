// src/components/ModalFormulario.tsx
import { useState } from "react";
import './Modal.css'

/**
 * Props del modal de creación de equipo.
 * - `onClose`: cierra el modal.
 * - `onSubmit`: entrega los datos del formulario al componente padre.
 */
interface Props {
  onClose: () => void;
  onSubmit: (data: { nombre: string; modelo: string; ip: string, idModbus: number }) => void;
}

/**
 * ModalFormulario.
 *
 * Maneja un formulario controlado para crear un nuevo equipo.
 * Al enviar:
 * - previene submit por defecto,
 * - llama `onSubmit` con los datos,
 * - cierra el modal.
 */
export default function ModalFormulario({ onClose, onSubmit }: Props) {
  const [nombre, setNombre] = useState("");
  const [modelo, setModelo] = useState("");
  const [ip, setIp] = useState("");
  const [idModbus, setIdModbus] = useState(1);

  /** Maneja envío del formulario y delega datos al padre. */
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({ nombre, modelo, ip, idModbus});
    onClose();
  };

  return (
    <div className="modal-overlay">
      <div className="modal">
        <h3>Agregar Equipo</h3>
        <form onSubmit={handleSubmit}>
          <input
            type="text"
            placeholder="Nombre"
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            required
          />
          <input
            type="text"
            placeholder="Modelo"
            value={modelo}
            onChange={(e) => setModelo(e.target.value)}
            required
          />
          <input
            type="text"
            placeholder="IP"
            value={ip}
            onChange={(e) => setIp(e.target.value)}
            required
          />
          <input
            type="number"
            placeholder="ID Modbus"
            value={idModbus}
            onChange={(e) => setIdModbus(Number(e.target.value))}
            required
          />
          <div className="modal-actions">
            <button type="submit">Guardar</button>
            <button type="button" onClick={onClose}>Cancelar</button>
          </div>
        </form>
      </div>
    </div>
  );
}