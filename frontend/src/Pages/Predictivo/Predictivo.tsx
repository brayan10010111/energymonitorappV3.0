import React, { useEffect, useRef, useState } from "react";
import "./Predictivo.css";
import GraficoPredictivo from "../../components/graficoPredictivo/graficoPredictivo";
import { fetchSistemas,  initSSEConnectionPredictivoTodoElDia,  type Sistema } from "../../db/db";


const Predictivo: React.FC = () => {
  const [estimar, setEstimar] = useState(false);
  const [sistemaSeleccionado, setSistemaSeleccionado] = useState<string>("");
  const [sistemas, setSistemas] = useState<Sistema[]>([]);
  const [estimado, setEstimado] = useState<number>(0);
  const Predecir = () => {
    if (!sistemaSeleccionado) {
      alert("Selecciona un sistema primero");
      return;
    }
    setEstimar(true);
  };

  useEffect(() => {
    const cargarSistemas = async () => {
      const data = await fetchSistemas();
      setSistemas(data);
    };
    cargarSistemas();
  }, []);

  const sourceRef = useRef<EventSource | null>(null);
  useEffect(() => {
      if (!sistemaSeleccionado || !estimar) return;
  
      console.log("Iniciando SSE para:", sistemaSeleccionado);
  
      const source = initSSEConnectionPredictivoTodoElDia(
        sistemaSeleccionado,
        setEstimado
      );
      console.log("IsetEstimado:", estimado);
      sourceRef.current = source;
  
      return () => {
        if (sourceRef.current) {
          sourceRef.current.close();
          sourceRef.current = null;
          console.log("Conexión SSE cerrada.");
        }
      };
    }, [sistemaSeleccionado, estimar]);

  return (
    <div className="energy-page">
      <h2 className="titulo">Predicción de Consumo de Energía</h2>

      <div className="formulario-predictivo">
        <div className="fila-predictivo">
          <label>Sistema de trabajo</label>
          <select
            className="selector"
            value={sistemaSeleccionado}
            onChange={(e) => setSistemaSeleccionado(e.target.value)}
          >
            <option value="">Seleccione un sistema</option>
            {sistemas.map((s) => (
              <option key={s.id} value={s.nombre}>
                {s.nombre}
              </option>
            ))}
          </select>
        </div>

        <div className="boton-container-predictivo">
          <button
            className="boton-generar-predictivo"
            disabled={!sistemaSeleccionado}
            onClick={Predecir}
          >
            Generar Predicción
          </button>
        </div>

        {estimar && (
          <div className="resultado-predictivo">
            <strong>Consumo de Energía Estimado:</strong> {estimado || 0} kWh
            <GraficoPredictivo
              estimar={estimar}
              sistema={sistemaSeleccionado}
            />
          </div>
        )}
      </div>
    </div>
  );
};

export default Predictivo;