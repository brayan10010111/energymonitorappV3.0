import "./TimeGraph.css";
import React, { useEffect, useState } from "react";
import { Line } from "react-chartjs-2";

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
} from "chart.js";
import axios from "axios";

// Importaciones de TIPOS
import type { ChartOptions, Plugin, ChartData } from "chart.js";
// import type { ChartOptions, Chart, Plugin, Point, ChartData } from "chart.js";

import zoomPlugin from "chartjs-plugin-zoom";

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
interface Equipo {
  id: number;
  nombre: string;
  modelo: string;
  ip: string;
  estado: string;
}

// Props del componente
interface TimeGraphProps {
  rangoFechas: [Date, Date] | null;
}
const MAX_DATA_POINTS = 60;
const TimeGraph: React.FC<TimeGraphProps> = ({ rangoFechas }) => {
  const [dataGraph, setDataGraph] = useState<number[]>(Array(24).fill(0));
  const [chartLabels, setChartLabels] = useState<string[]>(
    Array.from({ length: 24 }, (_, i) => i.toString().padStart(2, "0"))
  );

  // const [, setChartData] = useState<number[]>([]);
  // const [, setIsLoading] = useState(true);
  useEffect(() => {
    if (!rangoFechas) {
      // Caso inicial → última hora
      fetch("/api/get_last_hour_initial/")
        .then((res) => res.json())
        .then((initialData) => {
          setChartLabels(initialData.datos.map((d: any) => d.timestamp));
          setDataGraph(initialData.datos.map((d: any) => d.valor));
        });
    } else {
      const [inicio, fin] = rangoFechas;
      fetch(
        `/api/get_data_influx?inicio=${inicio.toISOString()}&fin=${fin.toISOString()}`
      )
        .then((res) => res.json())
        .then((data) => {
          setChartLabels(data.datos.map((d: any) => d.timestamp));
          setDataGraph(data.datos.map((d: any) => d.valor));
        });
    }
  }, [rangoFechas]);

  useEffect(() => {
    // Activar SSE solo en modo tiempo real
    if (rangoFechas !== null) return;

    const source = new EventSource("/api/graficas_update");

    source.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);

        // Escuchamos el nuevo tipo de evento
        if (payload.tipo === "grafico_punto_actualizado") {
          const newPoint: { label: string; value: number } = payload.contenido;

          // Lógica de la "Ventana Deslizante"
          setChartLabels((prevLabels) => {
            // Añade la nueva etiqueta al final y elimina la más antigua del principio
            const newLabels = [...prevLabels, newPoint.label];
            return newLabels.slice(-MAX_DATA_POINTS); // Mantiene el array con 60 elementos como máximo
          });

          setDataGraph((prevData) => {
            // Añade el nuevo valor y elimina el más antiguo
            const newData = [...prevData, newPoint.value];
            return newData.slice(-MAX_DATA_POINTS);
          });
        }
      } catch (err) {
        console.error("Error SSE:", err);
      }
    };

    source.onerror = (err) => {
      console.error("Error SSE:", err);
      source.close();
    };

    return () => {
      source.close();
      console.log("Conexión SSE cerrada.");
    };
  }, [rangoFechas]);

  // --- INICIO DE LA CORRECCIÓN ---
  // El objeto 'data' DEBE estar completamente definido aquí.
  // Utiliza el estado 'dataGraph' para poblar los datos del dataset.
  const data: ChartData<"line"> = {
    labels: chartLabels,
    datasets: [
      {
        label: "Consumo A",
        data: dataGraph, // Usando el estado aquí
        borderColor: "rgba(255, 247, 99, 0.7)",
        backgroundColor: "rgba(255, 247, 99, 0.3)",
        pointBackgroundColor: "rgba(255, 247, 99, 1)",
        pointRadius: 2,
        fill: true,
        tension: 0.4,
        spanGaps: false,
        stepped: false,
      },
    ],
  };

  const options: ChartOptions<"line"> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { position: "top" as const },
      title: {
        display: true,
        text: "Consumo de energía por hora",
        font: { family: "Roboto", size: 16 },
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
        },
      },
      y: {
        title: { display: true, text: "kWh" },
        beginAtZero: true,
        suggestedMin: 0,
        suggestedMax: Math.max(...dataGraph),
      },
    },
    // Es recomendable desactivar las animaciones para un gráfico en tiempo real fluido
    // animation: {
    //   duration: 250, // Una animación sutil
    // },
  };
  // --- FIN DE LA CORRECCIÓN ---

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
  // console.log("Labels:", chartLabels);
  // console.log("Data:", dataGraph);

  const [medidor, setMedidor] = useState<string>("");
  const [equipos, setEquipos] = useState<Equipo[]>([]);
  useEffect(() => {
    const fetchEquipos = async () => {
      try {
        const response = await axios.get("http://localhost:8000//api/equipos/");
        // console.log("Respuesta del backend:", response.data);
        setEquipos(
          Array.isArray(response.data)
            ? response.data
            : response.data.results || []
        );
      } catch (error) {
        console.error("Error al cargar equipos:", error);
      }
    };

    fetchEquipos();
  }, []);
  return (
    <div className="timegraph">
      <div >
        <select  className="selector" value={medidor} onChange={(e) => setMedidor(e.target.value)}>
          {equipos.map((m) => (
            <option key={m.id} value={m.nombre}>
              {m.nombre}
            </option>
          ))}
        </select>
      </div>
      <Line data={data} options={options} plugins={[cursorPlugin]} />
    </div>
  );
};

export default TimeGraph;
