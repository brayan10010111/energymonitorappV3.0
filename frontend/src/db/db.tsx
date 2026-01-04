// backend/src/db.ts
import axios from 'axios';


function getCookie(name: string): string | undefined {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) {
    const last = parts.pop();
    return last ? last.split(';').shift() : undefined;
  }
  return undefined;
}


export const guardarEquipo = async (equipo:Equipo) => {
  const API_URL = import.meta.env.VITE_API_URL;

  try {
    await axios.get(`${API_URL}/api/csrf/`, {
      withCredentials: true, // Esto permite que el navegador guarde la cookie
    });

    const csrfToken = getCookie('csrftoken');
    console.log('CSRF token:', csrfToken);
    console.log("Payload enviado:", equipo);
    const response = await axios.post(
      `${API_URL}/api/equipos/`,
      equipo,
      
      {
         headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken,
    },
    withCredentials: true,
  });

    console.log('Equipo guardado:', response.data);
  } catch (error) {
  if (axios.isAxiosError(error) && error.response) {
    console.error("Detalles del error:", error.response.data);
  } else {
    console.error("Error desconocido:", error);
  }
}
};


export const procesarDatos = (
  datos: any[],
  rangoFechas: [Date, Date] | null = null
) => {
  if (!datos || datos.length === 0) {
    let cantidad = 60; // por defecto 60 minutos
    let labels: string[] = [];

    const ahora = new Date();
    let inicio: Date;
    let fin: Date;

    if (rangoFechas) {
      [inicio, fin] = rangoFechas;
    } else {
      fin = ahora;
      inicio = new Date(fin.getTime() - 60 * 60000); // 1 hora atrás
    }

    const diffMs = fin.getTime() - inicio.getTime();
    const diffSeg = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffMs / 60000);
    const diffHoras = Math.floor(diffMs / 3600000);
    const diffDias = Math.floor(diffMs / (3600000 * 24));

    if (diffDias >= 1) {
      cantidad = diffDias + 1;
      labels = Array.from({ length: cantidad }, (_, i) => {
        const fecha = new Date(inicio.getTime() + i * 86400000);
        return fecha.toLocaleDateString("es-CO");
      });
    } else if (diffHoras > 1) {
      cantidad = diffHoras + 1;
      labels = Array.from({ length: cantidad }, (_, i) => {
        const hora = new Date(inicio.getTime() + i * 3600000);
        return hora.toLocaleString("es-CO", {
          hour: "2-digit",
          minute: "2-digit",
          hourCycle: "h23"
        });
      });
    } else if (diffHoras === 1) {
      cantidad = 60;
      labels = Array.from({ length: cantidad }, (_, i) => {
        const t = new Date(fin.getTime() - (cantidad - i) * 60000);
        return t.toLocaleString("es-CO", {
          hour: "2-digit",
          minute: "2-digit",
          hourCycle: "h23"
        });
      });
    } else if (diffMin <= 5) {
      cantidad = Math.ceil(diffSeg / 5);
      labels = Array.from({ length: cantidad }, (_, i) => {
        const t = new Date(fin.getTime() - (cantidad - i) * 5000);
        return t.toLocaleString("es-CO", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hourCycle: "h23"
        });
      });
    } else {
      cantidad = diffMin || 60;
      labels = Array.from({ length: cantidad }, (_, i) => {
        const t = new Date(inicio.getTime() + i * 60000);
        return t.toLocaleString("es-CO", {
          hour: "2-digit",
          minute: "2-digit",
          hourCycle: "h23"
        });
      });
    }

    return { labels, valores: Array(cantidad).fill(0) };
  }

  return {
    labels: datos.map((d) =>
      new Date(d.timestamp).toLocaleString("es-CO", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hourCycle: "h23"
        
      })
    ),
    valores: datos.map((d) => d.valor ?? 0),
  };
};

export const getInfluxData = async (
  medidor: string,
  variable: string,
  rangoFechas?: [Date, Date] 
) => {
  const apiUrl = import.meta.env.VITE_API_URL;
//   console.log(apiUrl);
  let url = "";

  if (!rangoFechas) {
    const fin = new Date(); // ahora
    const inicio = new Date(fin.getTime() - 5 * 60 * 1000); // 5 minutos atrás

    url = `${apiUrl}/api/get_data_influx?inicio=${inicio.toISOString()}&fin=${fin.toISOString()}&medidor=${medidor}&variable=${
      variable || "Voltage A-B"
    }`;
  } else {
    const [inicio, fin] = rangoFechas || [undefined, undefined];
    url = `${apiUrl}/api/get_data_influx?inicio=${inicio?.toISOString()}&fin=${fin?.toISOString()}&medidor=${medidor}&variable=${variable}`;
  }
//   console.log(url)
  const res = await fetch(url);
  return res.json();
};

export const initSSEConnectionPredictivo = (
  sistema: string,
  setDataGraph: React.Dispatch<React.SetStateAction<number[]>>
) => {
  const apiUrl = import.meta.env.VITE_API_URL;
  const source = new EventSource(
    `${apiUrl}/api/stream_predicciones/?sistema=${encodeURIComponent(sistema)}`
  );

  source.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);

      if (payload.tipo === "grafico_actualizado") {
        const nuevosDatos: { timestamp: string; valor: number }[] = payload.contenido;

        setDataGraph((prev) => {
          const updated = [...prev]; // 1440 posiciones

          nuevosDatos.forEach((d) => {
            const t = new Date(d.timestamp);
            const index = t.getHours() * 60 + t.getMinutes();

            if (index >= 0 && index < 1440) {
              updated[index] = d.valor ?? null;
            }
          });

          return updated;
        });
      }
    } catch (err) {
      console.error("Error SSE:", err);
    }
  };

  source.onerror = (err) => {
    console.error("Error SSE:", err);
  };

  return source;
};

export const initSSEConnection =(
  medidor: string,
  variable: string,
  setChartLabels: React.Dispatch<React.SetStateAction<string[]>>,
  setDataGraph: React.Dispatch<React.SetStateAction<number[]>>
) => {
  const MAX_DATA_POINTS = 60;
  const apiUrl = import.meta.env.VITE_API_URL;
  const source = new EventSource(
  `${apiUrl}/api/graficas_update/?medidor=${encodeURIComponent(medidor)}&variable=${encodeURIComponent(variable)}`
);

  source.onmessage = (event) => {
    console.log("Evento SSE crudo:", event.data);
    try {
      const payload = JSON.parse(event.data);
      console.log("Datos SSE recibidos:", payload);
        
      if (payload.tipo === "grafico_actualizado") {
        const nuevosDatos: { timestamp: string; valor: number }[] = payload.contenido;

        setChartLabels((prevLabels) => {
          const newLabels = [...prevLabels, ...nuevosDatos.map((d) =>{
            const t = new Date(d.timestamp);
            return t.toLocaleString("es-CO", {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
                hourCycle: "h23"
                });
          } )];
          return newLabels.slice(-MAX_DATA_POINTS);
        });

        setDataGraph((prevData) => {
          const newData = [...prevData, ...nuevosDatos.map((d) => d.valor ?? 0)];
          return newData.slice(-MAX_DATA_POINTS);
        });
      }
    } catch (err) {
      console.error("Error SSE:", err);
    }
  };

  source.onerror = (err) => {
    console.error("Error SSE:", err);
    };

  return source;
}

export const getAcumulados = async (rangoFechas: [Date, Date] | null = null, sistema: string) => {
  const apiUrl = import.meta.env.VITE_API_URL;
  const url = `${apiUrl}/api/get_acumulados?inicio=${rangoFechas ? rangoFechas[0].toISOString() : ''}&fin=${rangoFechas ? rangoFechas[1].toISOString() : ''}&sistema=${sistema}`;
  const res = await fetch(url);
  return res.json();
}

export interface Equipo {
  id?: number;
  nombre: string;
  modelo: string;
  ip: string;
  id_modbus: number;
  estado?: string;
}

export interface Variable {
  id: number;
  nombre: string;
  unidad: string;
  registro: string;
  tipo: string;
  subcategoria: number;
}

export interface Maquina {
  id: number;
  nombre: string;
  capacidad: string;
  unidad: string;
  sistema: number;
}

export interface Sistema {
  id: number;
  nombre: string;
  descripcion: string;
}

export const fetchEquipos = async (): Promise<Equipo[]> => {
  const apiUrl = import.meta.env.VITE_API_URL;
  try {
    const response = await axios.get(`${apiUrl}/api/equipos/`);
    return Array.isArray(response.data)
      ? response.data
      : response.data.results || [];
  } catch (error) {
    console.error("Error al cargar equipos:", error);
    return [];
  }
};

export const fetchVariables = async (): Promise<Variable[]> => {
  const apiUrl = import.meta.env.VITE_API_URL;
  try {
    const response = await axios.get(`${apiUrl}/api/variables/`);
    return Array.isArray(response.data)
      ? response.data
      : response.data.results || [];
  } catch (error) {
    console.error("Error al cargar variables:", error);
    return [];
  }
};

export const fetchMaquinas = async (): Promise<Maquina[]> => {
  const apiUrl = import.meta.env.VITE_API_URL;
  try {
    const response = await axios.get(`${apiUrl}/api/maquinas/`);
    return Array.isArray(response.data)
      ? response.data
      : response.data.results || [];
  } catch (error) {
    console.error("Error al cargar variables:", error);
    return [];
  }
};

export const fetchSistemas = async (): Promise<Sistema[]> => {
  const apiUrl = import.meta.env.VITE_API_URL;
  try {
    const response = await axios.get(`${apiUrl}/api/sistemas/`);
    return Array.isArray(response.data)
      ? response.data
      : response.data.results || [];
  } catch (error) {
    console.error("Error al cargar variables:", error);
    return [];
  }
};



export const initSSEConnectionPredictivoTodoElDia = (
  sistema: string,
  setEstimado: React.Dispatch<React.SetStateAction<number>>
) => {
  const apiUrl = import.meta.env.VITE_API_URL;

  const source = new EventSource(
    `${apiUrl}/api/stream_predicciones_dia/?sistema=${encodeURIComponent(sistema)}`
  );

  source.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);

      if (payload.tipo === "grafico_actualizado") {
        const total = payload.contenido.total_estimado_kWh;

        // total es un número, úsalo directamente
        setEstimado(total);
      }
    } catch (err) {
      console.error("Error SSE:", err);
    }
  };

  source.onerror = (err) => {
    console.error("Error SSE:", err);
  };

  return source;
};