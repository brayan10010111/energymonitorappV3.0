import "./Equipos.css";
import Dispositivo from "../../components/Dispositivo/Dispositivo";
import ModalFormulario from "../../components/Modal/Modal";
import { fetchEquipos, guardarEquipo } from "../../db/db";
import { useEffect, useState } from "react";
import type { Equipo } from "../../db/db";

/**
 * Vista de administración/listado de equipos.
 *
 * - Carga equipos desde el backend.
 * - Permite seleccionar uno o varios (checkbox por fila y select-all).
 * - Abre un modal para crear un equipo y lo envía al backend.
 */
const Equipos = () => {
  const [equipos, setEquipos] = useState<Equipo[]>([]);
  const [seleccionados, setSeleccionados] = useState<number[]>([]);
  const [selectAll, setSelectAll] = useState(false);
  const [mostrarModal, setMostrarModal] = useState(false);

  useEffect(() => {
    /** Carga inicial de equipos al montar la vista. */
    const cargar = async () => {
      const data = await fetchEquipos();
      setEquipos(data as Equipo[]);
    };

    cargar();
}, []);

  /** Alterna selección de todos los equipos listados. */
  const toggleSelectAll = () => {
    if (selectAll) {
      setSeleccionados([]);
    } else {
      setSeleccionados(
        equipos
          .map((e) => e.id)
          .filter((id): id is number => typeof id === "number")
      );
    }
    setSelectAll(!selectAll);
  };

  /** Alterna la selección de un equipo por id. */
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
            equipos
              .filter(
                (equipo): equipo is Equipo & { id: number } =>
                  typeof equipo.id === "number"
              )
              .map((equipo) => {
                const equipoNormalizado = {
                  ...equipo,
                  estado: equipo.estado ?? "offline",
                };

                return (
                  <Dispositivo
                    key={equipo.id}
                    equipo={equipoNormalizado}
                    seleccionado={seleccionados.includes(equipo.id)}
                    onToggle={toggleEquipo}
                  />
                );
              })}
        </tbody>
      </table>

      {mostrarModal && (
        <ModalFormulario
          onClose={() => setMostrarModal(false)}
          onSubmit={(data) => {
            /**
             * Crea el objeto `Equipo` localmente y lo envía al backend.
             *
             * Nota: aquí se calcula un id incremental en el frontend para
             * mantener la UI consistente; el backend también podría asignar id.
             */
            const ids = equipos
              .map((e) => e.id)
              .filter((id): id is number => typeof id === "number");

            const nextId = ids.length > 0 ? Math.max(...ids) + 1 : 1;

            const nuevoEquipo: Equipo = {
              id: nextId,
              nombre: data.nombre,
              modelo: data.modelo,
              ip: data.ip,
              id_modbus: data.idModbus,
              estado: "offline",
            };            
            // Envía la creación al backend (no bloqueante para la UI).
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
