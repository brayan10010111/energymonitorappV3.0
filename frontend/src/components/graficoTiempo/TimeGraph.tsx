import "./TimeGraph.css";
import React, { useEffect, useRef, useState } from "react";
import { Line } from "react-chartjs-2";
import {
  getInfluxData,
  procesarDatos,
  initSSEConnection,
  fetchEquipos,
  fetchVariables,
} from "../../db/db";

// Importaciones de VALORES
import {
  Chart as ChartJS,
  LineElement,
  PointElement,
  CategoryScale,
  LinearScale,
  Title,
  Tooltip,
  Legend,
  Filler,
  Chart,
} from "chart.js";

// Importaciones de TIPOS
import type { ChartOptions, Plugin, ChartData } from "chart.js";

import zoomPlugin from "chartjs-plugin-zoom";
import type { Equipo, Variable } from "../../db/db";
// Registrar componentes
ChartJS.register(
  LineElement,
  PointElement,
  CategoryScale,
  LinearScale,
  Title,
  Tooltip,
  Legend,
  Filler,
  zoomPlugin
);

// Extender tipos de Chart.js
declare module "chart.js" {
  interface Chart {
    cursor?: { x: number };
  }
}

interface TimeGraphProps {
  rangoFechas: [Date, Date] | null;
  autorefresh: boolean;
}

// Componente principal
const TimeGraph: React.FC<TimeGraphProps> = ({ rangoFechas, autorefresh }) => {
  const [dataGraph, setDataGraph] = useState<number[]>(Array(24).fill(0));
  const ahora = new Date();

  const [chartLabels, setChartLabels] = useState<string[]>(
    Array.from({ length: 60 }, (_, i) => {
      const t = new Date(ahora.getTime() - (59 - i) * 60000);
      return t.toLocaleTimeString("es-CO", {
        hour: "2-digit",
        minute: "2-digit",
        hourCycle: "h23",
      });
    })
  );

  const [variables, setVariables] = useState<Variable[]>([]);
  const [equipoSeleccionado, setEquipoSeleccionado] = useState<string>("");
  const [equipos, setEquipos] = useState<Equipo[]>([]);
  const [variablesSeleccionadas, setVariablesSeleccionadas] =
    useState<string>("");

  //SELECTOR DE equipoSeleccionadoES-----------------------------

  useEffect(() => {
    const cargarEquipos = async () => {
      const data = await fetchEquipos();
      setEquipos(data);
    };
    const cargarVariables = async () => {
      const data = await fetchVariables();
      setVariables(data);
    };
    cargarEquipos();
    cargarVariables();
  }, []);

  //---------------------------------------------------
  // Efecto de carga de datos
  useEffect(() => {
    if (variables.length > 0) {
      if (variablesSeleccionadas == "") {
        setVariablesSeleccionadas(variables[1].nombre);
      }
    }
    if (equipos.length > 0) {
      if (equipoSeleccionado == "") {
        setEquipoSeleccionado(equipos[0].nombre);
      }
    }
    if (!equipos || equipos.length === 0 || equipoSeleccionado === "") return;
    const fetchData = async () => {
      try {
        const data = await getInfluxData(
          equipoSeleccionado,
          variablesSeleccionadas,
          rangoFechas || undefined
        );
        const { labels, valores } = procesarDatos(
          data.datos,
          rangoFechas || null
        );
        setChartLabels([...labels]);
        setDataGraph([...valores]);
      } catch (error) {
        console.error("Error consultando Influx:", error);
      }
    };

    fetchData();
  }, [equipos, rangoFechas, equipoSeleccionado, variablesSeleccionadas]);

  //---------------------------------------------------
  // EFECTO DE SSE PARA DATOS EN TIEMPO REAL-----------------------------
  // Maneja la conexión SSE
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!equipoSeleccionado || !variablesSeleccionadas || !autorefresh) return;

    console.log(
      "Iniciando conexión SSE para equipoSeleccionado:",
      equipoSeleccionado
    );
    const source = initSSEConnection(
      equipoSeleccionado,
      variablesSeleccionadas,
      setChartLabels,
      setDataGraph
    );
    sourceRef.current = source;

    return () => {
      if (sourceRef.current) {
        sourceRef.current.close();
        sourceRef.current = null;
        console.log("Conexión SSE cerrada.");
      }
    };
  }, [equipoSeleccionado, variablesSeleccionadas, autorefresh]);

  // Maneja el cierre si autorefresh cambia a false
  useEffect(() => {
    if (!autorefresh && sourceRef.current) {
      console.log("Autorefresh desactivado, cerrando conexión.");
      sourceRef.current.close();
      sourceRef.current = null;
    }
  }, [autorefresh]);

  //---------------------------------------------------

  //CONFIGURACION DEL GRAFICO-----------------------------

  //DEFINICION DE DATOS Y ESTILOS DEL GRAFICO-----------------------------
  const data: ChartData<"line"> = {
    labels: chartLabels,
    datasets: [
      {
        label: equipoSeleccionado,
        data: dataGraph,
        borderColor: "rgba(255, 247, 99, 0.7)",
        backgroundColor: "rgba(255, 247, 99, 0.3)",
        pointBackgroundColor: "rgba(255, 247, 99, 1)",

        pointRadius: 3,
        pointHoverRadius: 5,
        borderWidth: 2,

        fill: true,
        tension: 0.4,
        spanGaps: false,
        stepped: false,
      },
    ],
  };
  //DEFINICION DE OPCIONES DEL GRAFICO-----------------------------
  const options: ChartOptions<"line"> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: "top" as const,
        labels: {
          color: "#ffffff",
        },
      },
      title: {
        display: true,
        text: "Consumo de energía en el tiempo",
        font: { family: "Roboto", size: 18 },
        color: "#ffffffff",
      },
      zoom: {
        pan: { enabled: true, mode: "x" },
        zoom: {
          drag: { enabled: true },
          wheel: { enabled: true },
          pinch: { enabled: true },
          mode: "x",
        },
      },
    },
    scales: {
      x: {
        title: {
          display: true,
          text: rangoFechas ? "Fecha y Hora" : "Última Hora (minutos)",
          color: "#ffffffff",
        },
        ticks: {
          color: "#d4d4d4ff",
          font: { family: "Roboto", size: 12 },
        },
      },
      y: {
        title: { display: true, text: "kWh", color: "#ffffffff" },
        beginAtZero: true,
        suggestedMin: 0,
        suggestedMax: Math.max(...dataGraph),

        ticks: {
          color: "#d4d4d4ff",
          font: { family: "Roboto", size: 14 },
        },
      },
    },
  };
  //DEFINICION PLUGIN CURSOR PERSONALIZADO-----------------------------
  const cursorPlugin: Plugin<"line"> = {
    id: "cursor",
    afterEvent: (chart, args) => {
      const { event } = args;
      if (event.x === null || event.y === null) {
        if (chart.cursor) {
          chart.cursor = undefined;
          if (chart.tooltip) {
            chart.tooltip.setActiveElements([], { x: 0, y: 0 });
          }
          chart.draw();
        }
        return;
      }
      const { tooltip } = chart;
      if (!tooltip) return;

      const {
        chartArea: { top, bottom, left, right },
      } = chart;
      const isMouseInsideChart =
        event.x >= left &&
        event.x <= right &&
        event.y >= top &&
        event.y <= bottom;

      if (event.type !== "mousemove" || !isMouseInsideChart) {
        if (chart.cursor) {
          chart.cursor = undefined;
          tooltip.setActiveElements([], { x: 0, y: 0 });
          chart.draw();
        }
        return;
      }
      const index = chart.scales.x.getValueForPixel(event.x);
      if (index === undefined) return;

      chart.cursor = { x: event.x };
      if (
        tooltip.getActiveElements().length > 0 &&
        tooltip.getActiveElements()[0].index === index
      ) {
        return;
      }

      const activeElements = chart.data.datasets
        .map((_, i) => {
          const meta = chart.getDatasetMeta(i);
          if (meta.data[index]) {
            return { datasetIndex: i, index };
          }
          return null;
        })
        .filter(
          (el): el is { datasetIndex: number; index: number } => el !== null
        );

      tooltip.setActiveElements(activeElements, { x: event.x, y: event.y });
      chart.draw();
    },
    afterDraw: (chart) => {
      if (chart.cursor) {
        const {
          ctx,
          chartArea: { top, bottom },
        } = chart;
        const x = chart.cursor.x;
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(x, top);
        ctx.lineTo(x, bottom);
        ctx.lineWidth = 2;
        ctx.strokeStyle = "rgba(241, 241, 241, 0.4)";
        ctx.stroke();
        ctx.restore();
      }
    },
  };
  //---------------------------------------------------

  Chart.defaults.devicePixelRatio = window.devicePixelRatio || 1;

  return (
    <div className="timegraph">
      <div className="selector-container">
        <select
          className="selector"
          value={equipoSeleccionado}
          onChange={(e) => setEquipoSeleccionado(e.target.value)}
        >
          {equipos.map((m) => (
            <option key={m.id} value={m.nombre}>
              {m.nombre}
            </option>
          ))}
        </select>
        <select
          className="selector"
          value={variablesSeleccionadas}
          onChange={(e) => setVariablesSeleccionadas(e.target.value)}
        >
          {variables.map((m) => (
            <option key={m.id} value={m.nombre}>
              {m.nombre}
            </option>
          ))}
        </select>
      </div>
      {/* <a>{variablesSeleccionadas}</a> */}
      <Line
        className="grafico-estilo"
        data={data}
        options={options}
        plugins={[cursorPlugin]}
      />
    </div>
  );
};

export default TimeGraph;
