import React, { useEffect, useRef, useState } from "react";
import TimeGraph from "../../components/graficoTiempo/TimeGraph";
import Grid from "../../components/Grid/Grid";
import "./Dashboard.css";
import { DateRangePicker } from "rsuite";
import { addDays, addHours, addMinutes, setHours, setMinutes } from "date-fns";
import { FaCalendarAlt } from "react-icons/fa";
import "rsuite/dist/rsuite.min.css";

/**
 * Props del Dashboard.
 * `collapsed` se usa para ajustar el layout cuando el sidebar está colapsado.
 */
type DashboardProps = {
  collapsed: boolean;
};

/**
 * Vista Dashboard.
 *
 * Responsabilidades:
 * - Permitir al usuario escoger un rango de fechas (DateRangePicker).
 * - Controlar el modo `autorefresh` (switch) que habilita/deshabilita SSE
 *   en los componentes de gráficas.
 * - Renderizar una grilla de gráficas `TimeGraph` que consumen Influx vía backend.
 */
const Dashboard: React.FC<DashboardProps> = ({ collapsed }) => {
  // const desdeInicial = setMinutes(setHours(hoy, 0), 0); // 00:00
  // const hastaInicial = setMinutes(setHours(hoy, 23), 59); // 23:59\
  const [mostrarDatepicker, setmostrarDatepicker] = useState(true);
  let mostrar = false;
  const [rango, setRango] = useState<[Date, Date] | null>(null);
  const [_, setIsManual] = useState(false);
  const pickerRef = useRef<any>(null);

  const [checked, setChecked] = useState(false);

  const ahora = new Date();

  /**
   * Abre el popup del DateRangePicker cuando el usuario hace click en el ícono.
   *
   * Nota: actualmente usa una variable local `mostrar`; el efecto visual depende
   * de que `pickerRef.current.open()` sea llamado.
   */
  const handleClick = () => {
    mostrar = !mostrar;
    if (mostrar) {
      if (pickerRef.current) {
        pickerRef.current.open(); // abre el popup del picker
      }
    }
  };

  const predefinedRanges: {
    label: string;
    value: [Date, Date];
    placement: "left" | "bottom" | undefined;
  }[] = [
    {
      label: "Últimos 5 minutos",
      value: [addMinutes(ahora, -5), ahora],
      placement: "left",
    },
    {
      label: "Últimos 30 minutos",
      value: [addMinutes(ahora, -30), ahora],
      placement: "left",
    },
    {
      label: "Última hora",
      value: [addHours(ahora, -1), ahora],
      placement: "left",
    },
    {
      label: "Últimas 8 horas",
      value: [addHours(ahora, -8), ahora],
      placement: "left",
    },
    {
      label: "Hoy",
      value: [
        setMinutes(setHours(ahora, 0), 0),
        setMinutes(setHours(ahora, 23), 59),
      ],
      placement: "left",
    },
    {
      label: "Ayer",
      value: [
        setMinutes(setHours(addDays(ahora, -1), 0), 0),
        setMinutes(setHours(addDays(ahora, -1), 23), 59),
      ],
      placement: "left",
    },
    {
      label: "Últimos 7 días",
      value: [addDays(ahora, -7), ahora],
      placement: "left",
    },
    {
      label: "Últimos 30 días",
      value: [addDays(ahora, -30), ahora],
      placement: "left",
    },
  ];

  useEffect(() => {
    /**
     * Evalúa el ancho de la ventana para decidir si se usa el DateRangePicker
     * completo (desktop) o el compacto (móvil).
     */
    const evaluarAncho = () => {
      setmostrarDatepicker(window.innerWidth > 768); // cambia el umbral según tu diseño
    };

    evaluarAncho(); // evalúa al montar

    window.addEventListener("resize", evaluarAncho); // actualiza al redimensionar

    return () => window.removeEventListener("resize", evaluarAncho);
  }, []);

  /**
   * Maneja la selección de rango.
   * - Si coincide con rangos rápidos (últimos 5/30 min, última hora, últimas 8h):
   *   respeta horas/minutos exactos.
   * - Si es manual (por calendario): normaliza a día completo (00:00 a 23:59).
   */
  const handleChange = (rangoSeleccionado: [Date, Date] | null) => {
    if (!rangoSeleccionado) return;

    // Detectar si el rango coincide con alguno de los rangos rápidos
    const esRangoRapido = predefinedRanges
      .slice(0, 4)
      .some(
        (r) =>
          r.value[0].getTime() === rangoSeleccionado[0].getTime() &&
          r.value[1].getTime() === rangoSeleccionado[1].getTime()
      );

    if (esRangoRapido) {
      setIsManual(false);
      setRango(rangoSeleccionado); // respeta la hora exacta
    } else {
      setIsManual(true);
      const desde = setMinutes(setHours(rangoSeleccionado[0], 0), 0);
      const hasta = setMinutes(setHours(rangoSeleccionado[1], 23), 59);
      setRango([desde, hasta]);
    }
  };
  // const [sidebarColapsado, setSidebarColapsado] = useState(false);

  /**
   * Controla el switch de autorefresh.
   * Cuando está activo, los `TimeGraph` abren SSE para actualizar el gráfico.
   */
  const handleSwitchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setChecked(event.target.checked);
  };

  return (
    <div className="app-container">
      <div
        className={`barra-supperior ${
          collapsed ? "sidebar-colapsado" : "sidebar-expandido"
        }`}
      >
        <div className="toggle-container">
          <p>autorefresh</p>
          <label className="switch">
            <input
              type="checkbox"
              checked={checked}
              onChange={handleSwitchChange}
            />
            <span className="slider" />
          </label>
        </div>

        <div className="date-picker">
          <button
            onClick={handleClick}
            style={{
              background: "none",
              cursor: "pointer",
            }}
          >
            <FaCalendarAlt size={21} />
          </button>

          {mostrarDatepicker ? (
            <DateRangePicker
              ref={pickerRef}
              value={rango}
              ranges={predefinedRanges}
              onChange={handleChange}
              onOk={handleChange}
              format="dd/MM/yyyy HH:mm"
              placement="bottomEnd"
              style={{
                right: 0,
                marginTop: 10,
                marginRight: 20,
                zIndex: 9999,
                position: "absolute",
                visibility: "hidden", // ← oculta sin romper funcionalidad
                pointerEvents: "none", // ← evita clics accidentales
              }}
            />
          ) : (
            <DateRangePicker
              oneTap
              showOneCalendar
              ref={pickerRef}
              value={rango}
              ranges={[]}
              onChange={handleChange}
              onOk={handleChange}
              format="dd/MM/yyyy HH:mm"
              placement="bottomEnd"
              style={{
                right: 0,
                marginTop: 10,
                marginRight: 20,

                position: "absolute",
                visibility: "hidden", // ← oculta sin romper funcionalidad
                pointerEvents: "none", // ← evita clics accidentales
              }}
            />
          )}
        </div>
      </div>
      <Grid>
        <TimeGraph rangoFechas={rango} autorefresh={checked} />
        <TimeGraph rangoFechas={rango} autorefresh={checked}/>
        <TimeGraph rangoFechas={rango} autorefresh={checked}/>
        <TimeGraph rangoFechas={rango} autorefresh={checked}/>
      </Grid>
    </div>
  );
};

export default Dashboard;
