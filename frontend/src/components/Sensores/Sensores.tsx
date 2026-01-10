import { useEffect, useState } from "react";
import { initSSEStreamSensores } from "../../db/db";

interface SensoresDashboardProps {
    sistema: string;
}


const SensoresDashboard: React.FC<SensoresDashboardProps> = ({ sistema }) =>  {
  const [sensorData, setSensorData] = useState<Record<string, number>>({});

  useEffect(() => {
    const source = initSSEStreamSensores(sistema,setSensorData);
    return () => source.close(); // Limpieza al desmontar
  }, []);

  const sensorKeys = Object.keys(sensorData);

  return (
    <div style={{ overflowX: "auto", padding: "1rem" }}>
      <table style={{ borderCollapse: "collapse", width: "100%" }}>
        <thead>
          <tr>
            {sensorKeys.map((sensor) => (
              <th key={sensor} style={{ border: "1px solid #ccc", padding: "2px", 
                fontSize:"1rem" }}>
                {sensor}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr>
            {sensorKeys.map((sensor) => (
              <td key={sensor} style={{ border: "1px solid #ccc", padding: "2px", 
                fontSize:"1rem"
              }}>
                {sensorData[sensor]?.toFixed(2)}
              </td>
            ))}
          </tr>
        </tbody>
      </table>
    </div>
  );
};

export default SensoresDashboard;