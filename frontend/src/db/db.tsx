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

interface Equipo {
  id: number;
  nombre: string;
  modelo: string;
  ip: string;
  estado: string;
}

export const guardarEquipo = async (equipo:Equipo) => {
  const API_URL = import.meta.env.VITE_API_URL;

  try {
    await axios.get('http://localhost:8000/api/csrf/', {
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