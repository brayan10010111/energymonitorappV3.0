// src/components/ModalFormulario.tsx
import { useState } from "react";
import './Modal.css'


interface Props {
  onClose: () => void;
  onSubmit: (data: { nombre: string; modelo: string; ip: string, idModbus: number }) => void;
}

export default function ModalFormulario({ onClose, onSubmit }: Props) {
  const [nombre, setNombre] = useState("");
  const [modelo, setModelo] = useState("");
  const [ip, setIp] = useState("");
  const [idModbus, setIdModbus] = useState(1);

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