import "./Informes.css";
// import { addDays, addHours, addMinutes, setHours, setMinutes } from "date-fns";
import { DateRangePicker } from "rsuite";
import "rsuite/dist/rsuite.min.css";
import { useEffect, useRef, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { FaCalendarAlt } from "react-icons/fa";
import EquiposModal from "../../components/EquiposModal/EquiposModal";
import VariablesModal from "../../components/VariablesModal/VariablesModal";
import {
  fetchEquipos,
  fetchInforme,
  fetchSubcategorias,
  fetchVariables,
} from "../../db/db";
import type { Equipo, Subcategoria, Variable } from "../../db/db";

type LayoutOutletContext = {
  collapsed: boolean;
  setCollapsed: (value: boolean) => void;
};

const Informes = () => {
  const { setCollapsed } = useOutletContext<LayoutOutletContext>();
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
      const result = await fetchInforme({
        nombreInforme,
        rango,
        equipos: medidoresSeleccionados,
        variables: variablesSeleccionadas,
        formato,
      });

      if (result.kind === "json") {
        const data = result.data;

        if (data?.error) {
          console.error("Error del backend:", data.error);
          alert(`Error generando informe: ${data.error}`);
          return;
        }

        if (data?.datos && Array.isArray(data.datos)) {
          setChartLabels(data.datos.map((d: any) => d.timestamp));
          setDataGraph(data.datos.map((d: any) => d.valor));
        } else {
          console.warn("Respuesta JSON inesperada:", data);
          alert("El backend no devolvió datos válidos para graficar.");
        }

        return;
      }

      const link = document.createElement("a");
      link.href = window.URL.createObjectURL(result.blob);
      link.download = result.filename;
      link.click();
    } catch (error) {
      console.error("Error generando informe:", error);
      alert("Hubo un problema al generar el informe.");
    }
  };

  useEffect(() => {
    const cargar = async () => {
      const data = await fetchEquipos();
      setEquipos(data);
    };
    cargar();
  }, []);

   useEffect(() => {
    const cargar = async () => {
      const data = await fetchVariables();
      setVariables(data);
    };
    cargar();
  }, []);

  let mostrar = false;
  const [subcategorias, setSubcategorias] = useState<Subcategoria[]>([]);
  useEffect(() => {
    const cargar = async () => {
      const data = await fetchSubcategorias();
      setSubcategorias(data);
    };
    cargar();
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
                onClick={() => {
                  setCollapsed(true);
                  setShowModalEquipos(true);
                }}
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
                onClick={() => {
                  setCollapsed(true);
                  setShowModalVariables(true);
                }}
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
