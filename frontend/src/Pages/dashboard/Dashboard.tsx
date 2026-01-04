import React, { useEffect, useRef, useState } from "react";
import TimeGraph from "../../components/graficoTiempo/TimeGraph";
import Grid from "../../components/Grid/Grid";
import "./Dashboard.css";
import { DateRangePicker } from "rsuite";
import { addDays, addHours, addMinutes, setHours, setMinutes } from "date-fns";
import { FaCalendarAlt } from "react-icons/fa";
import "rsuite/dist/rsuite.min.css";
type DashboardProps = {
  collapsed: boolean;
};



const Dashboard: React.FC<DashboardProps> = ({ collapsed }) => {
  // const desdeInicial = setMinutes(setHours(hoy, 0), 0); // 00:00
  // const hastaInicial = setMinutes(setHours(hoy, 23), 59); // 23:59\
  const [mostrarDatepicker, setmostrarDatepicker] = useState(true);
  let mostrar = false
  const [rango, setRango] = useState<[Date, Date] | null>(null);
  const [_, setIsManual] = useState(false);
  const pickerRef = useRef<any>(null);
  

  const ahora = new Date();
  const handleClick = () => {
    mostrar = !mostrar
    if(mostrar){
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
    const evaluarAncho = () => {
      setmostrarDatepicker(window.innerWidth > 768); // cambia el umbral según tu diseño
    };

    evaluarAncho(); // evalúa al montar

    window.addEventListener("resize", evaluarAncho); // actualiza al redimensionar

    return () => window.removeEventListener("resize", evaluarAncho);
  }, []);

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



  return (
    <div className="app-container">
      <div
        className={`barra-supperior ${
          collapsed ? "sidebar-colapsado" : "sidebar-expandido"
        }`}
      >
        <div className="date-picker">
          <button
            onClick={handleClick}
            style={{
              background: "none",
              cursor: "pointer",
            }}
          >
            <FaCalendarAlt  size={21} />
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
                marginTop:10,
                marginRight:20, 
                zIndex:9999,
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
                marginTop:10,
                marginRight:20,
                
                position: "absolute",
                visibility: "hidden", // ← oculta sin romper funcionalidad
                pointerEvents: "none", // ← evita clics accidentales
              }}
            />
          )}
        </div>
      </div>
      <Grid>
      
        <TimeGraph  rangoFechas={rango}/>
        <TimeGraph  rangoFechas={rango}/>
        <TimeGraph  rangoFechas={rango}/>
        <TimeGraph  rangoFechas={rango}/>
      </Grid>
    </div>
  );
};

export default Dashboard;
