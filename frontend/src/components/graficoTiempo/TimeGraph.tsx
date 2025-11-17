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

// Importaciones de TIPOS
import type { ChartOptions, Chart, Plugin, Point, ChartData } from "chart.js";

import "./TimeGraph.css";
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

// Props del componente
interface TimeGraphProps {
  rangoFechas: [Date, Date] | null;
}

const TimeGraph: React.FC<TimeGraphProps> = ({ rangoFechas }) => {
  const [dataGraph, setDataGraph] = useState<number[]>(Array(24).fill(0));

  useEffect(() => {
    interface InfluxDatum {
      timestamp: string;
      valor: number;
    }
    if (rangoFechas) {
      const [inicio, fin] = rangoFechas;
      fetch(`/api/get_data_influx?inicio=${inicio.toISOString()}&fin=${fin.toISOString()}`)
        .then((res) => res.json())
        .then((data: { datos: InfluxDatum[] }) => {
          const horasLocal = Array(24).fill(0);
          data.datos.forEach(({ timestamp, valor }) => {
            const hora = new Date(timestamp).getHours();
            horasLocal[hora] += valor;
          });
          setDataGraph(horasLocal);
        })
        .catch((err) => console.error("Error al consultar Influx:", err));
    }
  }, [rangoFechas]);

  // --- INICIO DE LA CORRECCIÓN ---
  // El objeto 'data' DEBE estar completamente definido aquí.
  // Utiliza el estado 'dataGraph' para poblar los datos del dataset.
  const data: ChartData<"line"> = {
    labels: Array.from({ length: 24 }, (_, i) => i.toString().padStart(2, "0")),
    datasets: [
      {
        label: "Consumo A",
        data: dataGraph, // Usando el estado aquí
        borderColor: "rgba(255, 247, 99, 0.7)",
        backgroundColor: "rgba(255, 247, 99, 0.3)",
        pointBackgroundColor: "rgba(255, 247, 99, 1)",
        pointRadius: 3,
        fill: true,
        tension: 0.4,
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
      x: { title: { display: true, text: "Hora del día" } },
      y: { title: { display: true, text: "kWh" } },
    },
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

      const { chartArea: { top, bottom, left, right } } = chart;
      const isMouseInsideChart = event.x >= left && event.x <= right && event.y >= top && event.y <= bottom;

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
      if (tooltip.getActiveElements().length > 0 && tooltip.getActiveElements()[0].index === index) {
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
        .filter((el): el is { datasetIndex: number; index: number } => el !== null);

      tooltip.setActiveElements(activeElements, { x: event.x, y: event.y });
      chart.draw();
    },
    afterDraw: (chart) => {
      if (chart.cursor) {
        const { ctx, chartArea: { top, bottom } } = chart;
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

  return (
    <div className="timegraph">
      <Line data={data} options={options} plugins={[cursorPlugin]} />
    </div>
  );
};

export default TimeGraph;