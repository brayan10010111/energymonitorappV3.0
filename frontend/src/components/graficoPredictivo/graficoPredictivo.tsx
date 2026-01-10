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
import { Line } from "react-chartjs-2";
// Importaciones de TIPOS
import type { ChartOptions, Plugin, ChartData } from "chart.js";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  getAcumulados,
  initSSEConnectionPredictivo,
  initSSEConnectionSistemas,
} from "../../db/db";
ChartJS.register(
  LineElement,
  PointElement,
  CategoryScale,
  LinearScale,
  Title,
  Tooltip,
  Legend,
  Filler
);

// Extender tipos de Chart.js
declare module "chart.js" {
  interface Chart {
    cursor?: { x: number };
  }
}

// Labels fijos del día (1440) — se calculan una sola vez.
const DAY_LABELS = Array.from({ length: 1440 }, (_, i) => {
  const h = Math.floor(i / 60).toString().padStart(2, "0");
  const m = (i % 60).toString().padStart(2, "0");
  return `${h}:${m}`;
});

/**
 * Props del gráfico predictivo.
 * - `estimar`: habilita/deshabilita modo predicción (y SSE asociado).
 * - `sistema`: nombre/identificador del sistema a consultar.
 */
interface GraficoPredictivoProps {
  estimar: boolean;
  sistema: string;   // ← CORREGIDO: ahora viene del padre
}

/**
 * Gráfico predictivo (día completo, 1440 puntos).
 *
 * Muestra dos series:
 * - Consumo real acumulado (cargado inicialmente + actualizado por SSE).
 * - Consumo estimado (actualizado por SSE cuando `estimar` está activo).
 */
const GraficoPredictivo: React.FC<GraficoPredictivoProps> = ({ estimar, sistema }) => {

  // 1440 minutos del día
  const [dataGraphPredicciones, setDataGraphPredicciones] = useState<number[]>(Array(1440).fill(null));
  const [dataGraphReal, setDataGraphReal] = useState<number[]>(Array(1440).fill(null));

  // SSE: dos conexiones distintas (real vs predicción). No reutilizar el mismo ref.
  const predSourceRef = useRef<EventSource | null>(null);
  const realSourceRef = useRef<EventSource | null>(null);

  // Cargar datos reales del día
  useEffect(() => {
    if (!sistema) return;

    /**
     * Consulta datos reales del día desde el backend (acumulados) y los mapea
     * al índice minuto-del-día (0..1439).
     */
    const cargarDatosReales = async () => {
      const ahora = new Date();
      const rangoFechas: [Date, Date] = [
        new Date(ahora.setHours(0, 0, 0, 0)),
        new Date()
      ];

      const json = await getAcumulados(rangoFechas, sistema);

      const real = Array(1440).fill(null);

      json.data.forEach((p: any) => {
        const fecha = new Date(p.time);
        const index = fecha.getHours() * 60 + fecha.getMinutes();
        if (index >= 0 && index < 1440) {
          real[index] = p.value;
        }
      });

      setDataGraphReal(real);
    };

    cargarDatosReales();
  }, [sistema]);

  // Iniciar SSE para predicciones
  useEffect(() => {
    if (!sistema || !estimar) return;

    // console.log("Iniciando SSE para:", sistema);

    const source = initSSEConnectionPredictivo(
      sistema,
      setDataGraphPredicciones
    );

    // Cerrar conexión previa si existía
    predSourceRef.current?.close();
    predSourceRef.current = source;

    return () => {
      predSourceRef.current?.close();
      predSourceRef.current = null;
    };
  }, [sistema]);

  // Cerrar SSE si estimar cambia a false
  useEffect(() => {
    if (!estimar) {
      predSourceRef.current?.close();
      predSourceRef.current = null;
      realSourceRef.current?.close();
      realSourceRef.current = null;
    }
  }, [estimar]);

  //---------------------------------------------------
  // EFECTO DE SSE PARA DATOS EN TIEMPO REAL-----------------------------
  //----------------------------------------------------
  useEffect(() => {
      if (!sistema || !estimar) return;
      // console.log("Iniciando SSE para datos reales de:", sistema);
      const source = initSSEConnectionSistemas(
        sistema,
        setDataGraphReal
      );
      realSourceRef.current?.close();
      realSourceRef.current = source;
  
      return () => {
        realSourceRef.current?.close();
        realSourceRef.current = null;
      };
    }, [sistema, estimar]);
  
    // Maneja el cierre si autorefresh cambia a false
    // (cierre ya manejado en el efecto anterior)

  const maxReal = useMemo(() => {
    const numeric = dataGraphReal.filter((v) => typeof v === "number") as number[];
    return numeric.length ? Math.max(...numeric) : 0;
  }, [dataGraphReal]);

  const data: ChartData<"line"> = useMemo(
    () => ({
      labels: DAY_LABELS,
      datasets: [
        {
          label: "Consumo Real",
          data: dataGraphReal,
        borderColor: "rgba(255, 247, 99, 0.7)",
        backgroundColor: "rgba(255, 247, 99, 0.3)",
        pointBackgroundColor: "rgba(255, 247, 99, 1)",
        pointRadius: 1, // más pequeño para 1440 puntos
        pointHoverRadius: 3,
        borderWidth: 1,
        fill: true,
        tension: 0.2,
        spanGaps: false,
        },
        {
          label: "Consumo Estimado",
          data: dataGraphPredicciones,
        borderColor: "rgba(99, 112, 255, 0.7)",
        backgroundColor: "rgba(133, 99, 255, 0.3)",
        pointBackgroundColor: "rgba(99, 130, 255, 1)",
        pointRadius: 1, // más pequeño para 1440 puntos
        pointHoverRadius: 3,
        borderWidth: 1,
        fill: true,
        tension: 0.2,
        spanGaps: false,
        },
      ],
    }),
    [dataGraphReal, dataGraphPredicciones]
  );

  const ahora = new Date();
  const minutoActual = ahora.getHours() * 60 + ahora.getMinutes(); // índice actual

  const options: ChartOptions<"line"> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: "top",
        labels: { color: "#ffffff" },
      },
      title: {
        display: true,
        text: "Grafico en tiempo real",
        font: { family: "Roboto", size: 18 },
        color: "#ffffffff",
      },
      tooltip: {
        callbacks: {
          label: (context) => {
            const label = context.dataset.label || "";
            const value = context.raw;

            if (value === null || value === undefined) {
              return `${label}: sin dato`;
            }

            return `${label}: ${value} kWh`;
          },
        },
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
        title: { display: true, text: "Minutos del día", color: "#ffffffff" },
        ticks: {
          color: "#d4d4d4ff",
          font: { family: "Roboto", size: 10 },
          autoSkip: true,
        },
        min: minutoActual - 60 >= 0 ? minutoActual - 60 : 0,
        max: minutoActual+60,
      },
      y: {
        title: { display: true, text: "kWh", color: "#ffffffff" },
        beginAtZero: true,
        suggestedMin: 0,
        suggestedMax: maxReal,
        ticks: {
          color: "#d4d4d4ff",
          font: { family: "Roboto", size: 12 },
        },
      },
    },
  };

  /**
   * Plugin de cursor vertical para mejorar lectura con 1440 puntos.
   * Activa tooltip y dibuja línea vertical siguiendo el mouse.
   */
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
  return (
    <div className="timegraph">
      <Line
        className="grafico-estilo"
        data={data}
        options={options}
        plugins={[cursorPlugin]}
      />
    </div>
  );
};

export default GraficoPredictivo;
