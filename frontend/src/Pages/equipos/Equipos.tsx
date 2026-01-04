import "./Equipos.css";
import Dispositivo from "../../components/Dispositivo/Dispositivo";
import ModalFormulario from "../../components/Modal/Modal";
import { guardarEquipo } from "../../db/db";
import { useEffect, useState } from "react";
import axios from "axios";

interface Equipo {
  id: number;
  nombre: string;
  modelo: string;
  ip: string;
  id_modbus: number;
  estado: string;
}

const Equipos = () => {
  const [equipos, setEquipos] = useState<Equipo[]>([]);
  const [seleccionados, setSeleccionados] = useState<number[]>([]);
  const [selectAll, setSelectAll] = useState(false);
  const [mostrarModal, setMostrarModal] = useState(false);

  useEffect(() => {
  const fetchEquipos = async () => {
    try {
      const response = await axios.get("http://localhost:8000/api/equipos/");
      // console.log("Respuesta del backend:", response.data);
      setEquipos(Array.isArray(response.data) ? response.data : response.data.results || []);
    } catch (error) {
      console.error("Error al cargar equipos:", error);
    }
  };

  fetchEquipos();
}, []);

  const toggleSelectAll = () => {
    if (selectAll) {
      setSeleccionados([]);
    } else {
      setSeleccionados(equipos.map((e) => e.id));
    }
    setSelectAll(!selectAll);
  };

  const toggleEquipo = (id: number) => {
    setSeleccionados((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    );
  };

  return (
    <div className="equipos-page">
      <table className="equipos-table">
        <thead>
          <tr>
            <th>
              <input
                className="check-style"
                type="checkbox"
                checked={selectAll}
                onChange={toggleSelectAll}
              />
            </th>
            <th>Nombre</th>
            <th>Modelo</th>
            <th>IP</th>
            <th>ID Modbus</th>
            <th>Estado</th>
            <th className="header-actions">
              <button
                className="add-button"
                onClick={() => setMostrarModal(true)}
              >
                +
              </button>
            </th>
          </tr>
        </thead>
        <tbody>
          {Array.isArray(equipos) &&
            equipos.map((equipo) => (
              <Dispositivo
                key={equipo.id}
                equipo={equipo}
                seleccionado={seleccionados.includes(equipo.id)}
                onToggle={toggleEquipo}
              />
            ))}
        </tbody>
      </table>

      {mostrarModal && (
        <ModalFormulario
          onClose={() => setMostrarModal(false)}
          onSubmit={(data) => {
            const nextId =
              equipos.length > 0
                ? Math.max(...equipos.map((e) => e.id)) + 1
                : 1;
            const nuevoEquipo: Equipo = {
              id: nextId,
              nombre: data.nombre,
              modelo: data.modelo,
              ip: data.ip,
              id_modbus: data.idModbus,
              estado: "offline",
            };            
            guardarEquipo(nuevoEquipo);
            setEquipos((prev) => [...prev, nuevoEquipo]);
            setMostrarModal(false);
          }}
        />
      )}
    </div>
  );
};

export default Equipos;
