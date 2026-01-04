import "./Informes.css";
// import { addDays, addHours, addMinutes, setHours, setMinutes } from "date-fns";
import { DateRangePicker } from "rsuite";
import "rsuite/dist/rsuite.min.css";
import { useEffect, useRef, useState } from "react";
import { FaCalendarAlt } from "react-icons/fa";
import axios from "axios";
import EquiposModal from "../../components/EquiposModal/EquiposModal";
import VariablesModal from "../../components/VariablesModal/VariablesModal";
import type { Equipo, Variable } from  "../../db/db";
// interface Equipo {
//   id: number;
//   nombre: string;
//   modelo: string;
//   ip: string;
//   estado: string;
// }

const Informes = () => {
  const pickerRef = useRef<any>(null);
  const [_, setChartLabels] = useState<string[]>([]);
  const [__, setDataGraph] = useState<number[]>([]);
  // Estado para el rango de fechas
  const [rango, setRango] = useState<[Date, Date] | null>(null);

  // Estado para equipos seleccionados
  const [medidoresSeleccionados, setMedidoresSeleccionados] = useState<
    string[]
  >([]);

  // Estado para formato de archivo
  const [formato, setFormato] = useState<"xlsx" | "csv">("xlsx");

  // Estado para nombre del informe
  const [nombreInforme, setNombreInforme] = useState("");
  const [variables, setVariables] = useState<Variable[]>([]);
  // Lista de equipos desde el backend
  const [equipos, setEquipos] = useState<Equipo[]>([]);
  const [showModalEquipos, setShowModalEquipos] = useState(false);
  const [showModalVariables, setShowModalVariables] = useState(false);

  const generarInforme = async () => {
  try {
    const params = new URLSearchParams();

    if (nombreInforme) params.append("nombreInforme", nombreInforme);

    if (rango && rango.length === 2) {
      params.append("fechaInicio", rango[0].toISOString());
      params.append("fechaFin", rango[1].toISOString());
    }

    if (medidoresSeleccionados.length > 0) {
      params.append("equipos", medidoresSeleccionados.join(","));
    }

    if (variablesSeleccionadas.length > 0) {
      params.append("variables", variablesSeleccionadas.join(","));
    }

    if (formato) params.append("formato", formato);

    const url = `/api/get_query_inform/?${params.toString()}`;
    const res = await fetch(url);

    const contentType = res.headers.get("content-type");

    if (contentType && contentType.includes("application/json")) {
      const data = await res.json();

      if (data.error) {
        // Manejo de error JSON
        console.error("Error del backend:", data.error);
        alert(`Error generando informe: ${data.error}`);
        return;
      }

      if (data.datos && Array.isArray(data.datos)) {
        setChartLabels(data.datos.map((d: any) => d.timestamp));
        setDataGraph(data.datos.map((d: any) => d.valor));
      } else {
        console.warn("Respuesta JSON inesperada:", data);
        alert("El backend no devolvió datos válidos para graficar.");
      }
    } else {
      // Caso archivo (CSV/XLSX): descargar
      const blob = await res.blob();
      const link = document.createElement("a");
      link.href = window.URL.createObjectURL(blob);
      link.download = `${nombreInforme || "informe"}.${formato}`;
      link.click();
    }
  } catch (error) {
    console.error("Error generando informe:", error);
    alert("Hubo un problema al generar el informe.");
  }
};

  useEffect(() => {
    const fetchEquipos = async () => {
      try {
        const response = await axios.get("http://localhost:8000/api/equipos/");
        const data = Array.isArray(response.data)
          ? response.data
          : response.data.results || [];
        setEquipos(data);
      } catch (error) {
        console.error("Error al cargar equipos:", error);
      }
    };
    fetchEquipos();
  }, []);

   useEffect(() => {
    const fetchEquipos = async () => {
      try {
        const response = await axios.get("http://localhost:8000/api/variables/");
        const data = Array.isArray(response.data)
          ? response.data
          : response.data.results || [];
        setVariables(data);
      } catch (error) {
        console.error("Error al cargar variables:", error);
      }
    };
    fetchEquipos();
  }, []);

  let mostrar = false;
const [subcategorias, setSubcategorias] = useState<Array<{ id: number; nombre: string; }>>([]);
useEffect(() => {
    const fetchEquipos = async () => {
      try {
        const response = await axios.get("http://localhost:8000/api/subcategorias/");
        const data = Array.isArray(response.data)
          ? response.data
          : response.data.results || [];
        setSubcategorias(data);
      } catch (error) {
        console.error("Error al cargar subcategorias:", error);
      }
    };
    fetchEquipos();
  }, []);
  const handleClick = () => {
    mostrar = !mostrar;
    if (mostrar) {
      if (pickerRef.current) {
        pickerRef.current.open(); // abre el popup del picker
      }
    }
  };

  const toggleMedidor = (nombre: string) => {
    setMedidoresSeleccionados((prev) =>
      prev.includes(nombre)
        ? prev.filter((m) => m !== nombre)
        : [...prev, nombre]
    );
  };
  // Seleccionar / Deseleccionar todos
  const toggleTodos = () => {
    if (medidoresSeleccionados.length === equipos.length) {
      setMedidoresSeleccionados([]);
    } else {
      setMedidoresSeleccionados(equipos.map((e) => e.nombre));
    }
  };
  const [variablesSeleccionadas, setVariablesSeleccionadas] = useState<
    string[]
  >([]);
  const toggleVariable = (nombre: string) => {
    setVariablesSeleccionadas((prev) =>
      prev.includes(nombre)
        ? prev.filter((v) => v !== nombre)
        : [...prev, nombre]
    );
  };

  const toggleTodasVariables = () => {
    if (variablesSeleccionadas.length === variables.length) {
      setVariablesSeleccionadas([]);
    } else {
      setVariablesSeleccionadas(variables.map((v) => v.nombre));
    }
  };

  const formatoRango = () => {
    if (!rango || !rango[0] || !rango[1]) return "";
    const inicio =
      rango[0].toLocaleDateString("es-ES") +
      " " +
      rango[0].toLocaleTimeString("es-ES", {
        hour: "2-digit",
        minute: "2-digit",
      });
    const fin =
      rango[1].toLocaleDateString("es-ES") +
      " " +
      rango[1].toLocaleTimeString("es-ES", {
        hour: "2-digit",
        minute: "2-digit",
      });
    return `${inicio} - ${fin}`;
  };

  return (
    <div className="main-content-informes">
      <h2 className="texto-informe">Generar Informe</h2>

      <table className="tabla-formulario">
        <tbody>
          <tr>
            <td>
              <strong className="columna1">Nombre del informe</strong>
            </td>
            <td className="columna2">
              <input
                className="columna2-input"
                type="text"
                value={nombreInforme}
                onChange={(e) => setNombreInforme(e.target.value)}
                placeholder="Escribe un nombre..."
              />
            </td>
          </tr>

          {/* Rango de fechas */}
          <tr>
            <td>
              <strong className="columna1">Rango de fechas</strong>
            </td>
            <td className="columna2">
              <div className="fecha-wrapper">
                <input
                  readOnly
                  className="input-fecha-display"
                  value={formatoRango()}
                  placeholder="Seleccionar rango..."
                />
                <div className="date-picker">
                  <button onClick={handleClick} className="btn-calendario">
                    <FaCalendarAlt size={21} />
                  </button>

                  <DateRangePicker
                    ref={pickerRef}
                    value={rango as [Date, Date]}
                    onChange={(value) => setRango(value)}
                    format="dd/MM/yyyy HH:mm"
                    placement="bottomEnd"
                    cleanable={false}
                    style={{
                      position: "absolute",
                      visibility: "hidden",
                      pointerEvents: "none",
                    }}
                  />
                </div>
              </div>
            </td>
          </tr>

          {/* Selección de equipos */}
          <tr>
            <td>
              <strong className="columna1">Equipos</strong>
            </td>
            <td className="columna2">
              <button
                onClick={() => setShowModalEquipos(true)}
                className="btn-abrir-modal"
              >
                Seleccionar equipos
              </button>
              {showModalEquipos && (
                <EquiposModal
                  equipos={equipos}
                  medidoresSeleccionados={medidoresSeleccionados}
                  toggleMedidor={toggleMedidor}
                  toggleTodos={toggleTodos}
                  onClose={() => setShowModalEquipos(false)}
                />
              )}
              <span className="texto-seleccion">
                {medidoresSeleccionados.length} seleccionados
              </span>
            </td>
          </tr>

          {/* Selección de variables */}
          <tr>
            <td>
              <strong className="columna1">Variables</strong>
            </td>
            <td className="columna2">
              <button
                onClick={() => setShowModalVariables(true)}
                className="btn-abrir-modal"
              >
                Seleccionar variables
              </button>
              {showModalVariables && (
                <VariablesModal
                  variables={variables}
                  variablesSeleccionadas={variablesSeleccionadas}
                  subcategorias={subcategorias}
                  toggleVariable={toggleVariable}
                  toggleTodasVariables={toggleTodasVariables}
                  onClose={() => setShowModalVariables(false)}
                />
              )}
              <span className="texto-seleccion">
                {variablesSeleccionadas.length} seleccionadas
              </span>
            </td>
          </tr>

          {/* Formato de archivo */}
          <tr>
            <td>
              <strong className="columna1">Formato</strong>
            </td>
            <td
              className="columna2 "
              style={{ display: "flex", marginTop: "1rem" }}
            >
              <label className="texto-toggle">
                <input
                  type="radio"
                  checked={formato === "xlsx"}
                  onChange={() => setFormato("xlsx")}
                />
                XLSX
              </label>
              <label className="texto-toggle" style={{ marginLeft: "1rem" }}>
                <input
                  type="radio"
                  checked={formato === "csv"}
                  onChange={() => setFormato("csv")}
                />
                CSV
              </label>
            </td>
          </tr>

          {/* Botón de generar */}
          <tr>
            <td colSpan={2} style={{ textAlign: "center" }}>
              <button onClick={generarInforme} className="btn-generar">
                Generar Informe
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
};

export default Informes;
