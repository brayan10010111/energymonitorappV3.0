/**
 * Capa de acceso a datos (frontend).
 *
 * Este módulo centraliza:
 * - Resolución de URL base del backend (por variable de entorno o localhost).
 * - Llamados HTTP (axios/fetch) a endpoints Django.
 * - Helpers de formateo de series temporales.
 * - Conexiones SSE (Server-Sent Events) para gráficas en tiempo real.
 */
import axios from 'axios';

/**
 * Obtiene la URL base del backend desde `VITE_API_URL`.
 *
 * Si no existe la variable de entorno, usa `http://localhost:8000`.
 */
const getApiUrl = () => {
  return import.meta.env.VITE_API_URL || "http://localhost:8000";
};

/**
 * Lee una cookie del navegador por nombre.
 *
 * Usado principalmente para recuperar `csrftoken` (Django) luego de llamar `/api/csrf/`.
 */
function getCookie(name: string): string | undefined {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) {
    const last = parts.pop();
    return last ? last.split(';').shift() : undefined;
  }
  return undefined;
}

/**
 * Crea/guarda un equipo en el backend.
 *
 * Flujo:
 * 1) Solicita cookie CSRF a Django (`/api/csrf/`) con `withCredentials`.
 * 2) Lee `csrftoken` desde cookies.
 * 3) Envía el payload del equipo a `/api/equipos/` con header `X-CSRFToken`.
 */
export const guardarEquipo = async (equipo:Equipo) => {
  const API_URL = getApiUrl();

  try {
    await axios.get(`${API_URL}/api/csrf/`, {
      withCredentials: true, // Esto permite que el navegador guarde la cookie
    });

    const csrfToken = getCookie('csrftoken');
    // console.log('CSRF token:', csrfToken);
    // console.log("Payload enviado:", equipo);
    await axios.post(
      `${API_URL}/api/equipos/`,
      equipo,
      
      {
         headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken,
    },
    withCredentials: true,
  });

    // console.log('Equipo guardado:', response.data);
  } catch (error) {
  if (axios.isAxiosError(error) && error.response) {
    console.error("Detalles del error:", error.response.data);
  } else {
    console.error("Error desconocido:", error);
  }
}
};

/**
 * Normaliza una serie temporal de mediciones para gráficas.
 *
 * - Si `datos` está vacío, genera una serie de ceros y labels con base en `rangoFechas`.
 * - Si `datos` tiene valores, mapea `timestamp` a labels y `valor` a valores.
 *
 * @param datos Lista de puntos con al menos `timestamp` y opcionalmente `valor`.
 * @param rangoFechas Rango [inicio, fin] opcional para construir labels cuando no hay datos.
 */
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

/**
 * Consulta datos históricos en InfluxDB a través del backend.
 *
 * Si no se envía rango, consulta los últimos 5 minutos.
 *
 * @param medidor Identificador del medidor/equipo.
 * @param variable Variable a consultar (si está vacío, usa "Voltage A-B").
 * @param rangoFechas Rango [inicio, fin] opcional.
 */
export const getInfluxData = async (
  medidor: string,
  variable: string,
  rangoFechas?: [Date, Date] 
) => {
  const apiUrl = getApiUrl();
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

/**
 * Abre una conexión SSE para predicciones (modo gráfico parcial/actualizado).
 *
 * Espera eventos JSON con forma:
 * - `tipo === "grafico_actualizado"`
 * - `contenido` como lista de puntos `{ timestamp, valor }`
 *
 * Actualiza `setDataGraph` en el índice minuto-del-día (0..1439).
 *
 * @returns `EventSource` para poder cerrarlo desde el componente (ej. `source.close()`).
 */
export const initSSEConnectionPredictivo = (
  sistema: string,
  setDataGraph: React.Dispatch<React.SetStateAction<number[]>>
) => {
  const apiUrl = getApiUrl();
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

/**
 * Abre una conexión SSE para actualizaciones de una gráfica (tiempo real).
 *
 * Mantiene una ventana deslizante de `MAX_DATA_POINTS` (60 por defecto).
 *
 * @param medidor Medidor/equipo fuente.
 * @param variable Variable a graficar.
 * @param setChartLabels Setter React para el eje X.
 * @param setDataGraph Setter React para el eje Y.
 * @returns `EventSource` para poder cerrarlo desde el componente.
 */
export const initSSEConnection =(
  medidor: string,
  variable: string,
  setChartLabels: React.Dispatch<React.SetStateAction<string[]>>,
  setDataGraph: React.Dispatch<React.SetStateAction<number[]>>
) => {
  const MAX_DATA_POINTS = 60;
  const apiUrl = getApiUrl();
  const source = new EventSource(
  `${apiUrl}/api/graficas_update/?medidor=${encodeURIComponent(medidor)}&variable=${encodeURIComponent(variable)}`
);

  source.onmessage = (event) => {
    // console.log("Evento SSE crudo:", event.data);
    try {
      const payload = JSON.parse(event.data);
      // console.log("Datos SSE recibidos:", payload);
        
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

/**
 * Consulta acumulados (kWh u otra métrica) para un rango y sistema.
 *
 * Si `rangoFechas` es null, envía parámetros vacíos (backend decide el rango por defecto).
 */
export const getAcumulados = async (rangoFechas: [Date, Date] | null = null, sistema: string) => {
  const apiUrl = getApiUrl();
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

export interface Subcategoria {
  id: number;
  nombre: string;
}

export type InformeFormato = "xlsx" | "csv";

export type InformeResult =
  | { kind: "json"; data: any }
  | { kind: "file"; blob: Blob; filename: string };

/**
 * Solicita al backend un informe armado (JSON o archivo).
 *
 * El endpoint puede responder:
 * - JSON (ej. errores, mensajes o reportes resumidos)
 * - Archivo binario (xlsx/csv)
 *
 * @returns Un discriminated-union: `{ kind: "json" }` o `{ kind: "file" }`.
 */
export const fetchInforme = async (params: {
  nombreInforme?: string;
  rango?: [Date, Date] | null;
  equipos?: string[];
  variables?: string[];
  formato?: InformeFormato;
}): Promise<InformeResult> => {
  const apiUrl = getApiUrl();

  const search = new URLSearchParams();
  if (params.nombreInforme) search.append("nombreInforme", params.nombreInforme);
  if (params.rango && params.rango.length === 2) {
    search.append("fechaInicio", params.rango[0].toISOString());
    search.append("fechaFin", params.rango[1].toISOString());
  }
  if (params.equipos && params.equipos.length > 0) {
    search.append("equipos", params.equipos.join(","));
  }
  if (params.variables && params.variables.length > 0) {
    search.append("variables", params.variables.join(","));
  }
  if (params.formato) search.append("formato", params.formato);

  const url = `${apiUrl}/api/get_query_inform/?${search.toString()}`;
  const res = await fetch(url, { credentials: "include" });

  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return { kind: "json", data: await res.json() };
  }

  const blob = await res.blob();
  const filename = `${params.nombreInforme || "informe"}.${params.formato || "xlsx"}`;
  return { kind: "file", blob, filename };
};

/**
 * Lista equipos desde el backend.
 *
 * Soporta respuestas en formato lista plana o paginada (`results`).
 */
export const fetchEquipos = async (): Promise<Equipo[]> => {
  const apiUrl = getApiUrl();
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

/**
 * Lista variables desde el backend.
 *
 * Soporta respuestas en formato lista plana o paginada (`results`).
 */
export const fetchVariables = async (): Promise<Variable[]> => {
  const apiUrl = getApiUrl();
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

/**
 * Lista subcategorías desde el backend.
 *
 * Soporta respuestas en formato lista plana o paginada (`results`).
 */
export const fetchSubcategorias = async (): Promise<Subcategoria[]> => {
  const apiUrl = getApiUrl();
  try {
    const response = await axios.get(`${apiUrl}/api/subcategorias/`);
    return Array.isArray(response.data)
      ? response.data
      : response.data.results || [];
  } catch (error) {
    console.error("Error al cargar subcategorias:", error);
    return [];
  }
};

/**
 * Lista máquinas desde el backend.
 *
 * Soporta respuestas en formato lista plana o paginada (`results`).
 */
export const fetchMaquinas = async (): Promise<Maquina[]> => {
  const apiUrl = getApiUrl();
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

/**
 * Lista sistemas desde el backend.
 *
 * Soporta respuestas en formato lista plana o paginada (`results`).
 */
export const fetchSistemas = async (): Promise<Sistema[]> => {
  const apiUrl = getApiUrl();
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



/**
 * Abre una conexión SSE para predicción del total estimado del día.
 *
 * Espera eventos JSON con forma:
 * - `tipo === "grafico_actualizado"`
 * - `contenido.total_estimado_kWh` numérico
 */
export const initSSEConnectionPredictivoTodoElDia = (
  sistema: string,
  setEstimado: React.Dispatch<React.SetStateAction<number>>
) => {
  const apiUrl = getApiUrl();

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


/**
 * Abre una conexión SSE para gráficas por sistema (actualización minuto-del-día).
 *
 * Calcula el índice como `hora*60 + minuto` y actualiza solo ese punto.
 */
export const initSSEConnectionSistemas = (
  sistema: string,
  setDataGraph: React.Dispatch<React.SetStateAction<number[]>>
) => {
  const apiUrl = getApiUrl();

  const source = new EventSource(
    `${apiUrl}/api/graficas_update_sistemas/?sistema=${encodeURIComponent(sistema)}`
  );

  source.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);

      if (payload.tipo === "grafico_actualizado") {
        const nuevosDatos: { timestamp: string; valor: number }[] = payload.contenido;

        setDataGraph((prevData) => {
          const updated = [...prevData];

          nuevosDatos.forEach((d) => {
            const t = new Date(d.timestamp);

            const minuteIndex = t.getHours() * 60 + t.getMinutes();

            // Actualizar solo ese punto
            updated[minuteIndex] = d.valor ?? 0;
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
