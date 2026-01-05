import { useState} from 'react'
import React from 'react'
import './VariablesModal.css';

/**
 * Props del modal de selección de variables.
 *
 * - `variables` y `subcategorias` se usan para agrupar y renderizar.
 * - `variablesSeleccionadas` vive en el padre.
 * - `toggleVariable` y `toggleTodasVariables` actualizan la selección en el padre.
 */
interface VariablesModalProps {
  variables: Array<{ id: number; nombre: string; unidad: string; registro: string; tipo: string; subcategoria: number }>;
  variablesSeleccionadas: string[];
  subcategorias: Array<{ id: number; nombre: string }>;
  toggleVariable: (nombre: string) => void;
  toggleTodasVariables: () => void;
  onClose: () => void;
}

/**
 * Agrupa el listado de variables por nombre de subcategoría.
 *
 * Si no encuentra subcategoría para una variable, genera un fallback
 * `Subcategoria {id}`.
 */
const agruparPorSubcategoria = (
  variables: Array<{ id: number; nombre: string; unidad: string; registro: string; tipo: string; subcategoria: number }>,
  subcategorias: Array<{ id: number; nombre: string }>
) => {
  return variables.reduce((acc, variable) => {
    // Buscar la subcategoría correspondiente
    const subcat = subcategorias.find((s) => s.id === variable.subcategoria);

    // Si existe, usamos su nombre; si no, dejamos el id como fallback
    const subcatNombre = subcat ? subcat.nombre : `Subcategoria ${variable.subcategoria}`;

    if (!acc[subcatNombre]) {
      acc[subcatNombre] = [];
    }
    acc[subcatNombre].push(variable);

    return acc;
  }, {} as Record<string, Array<{ id: number; nombre: string; unidad: string; registro: string; tipo: string; subcategoria: number }>>);
};

/**
 * Modal para seleccionar variables, agrupadas por subcategoría.
 *
 * Incluye expansión/colapso por subcategoría y selección múltiple.
 */
const VariablesModal: React.FC<VariablesModalProps> = ({
  variables,
  variablesSeleccionadas,
  subcategorias,
  toggleVariable,
  toggleTodasVariables,
  onClose,
}) => {
  const variablesPorSubcategoria = agruparPorSubcategoria(variables,subcategorias);
const [subcategoriasAbiertas, setSubcategoriasAbiertas] = useState<string[]>([]);

/** Alterna expansión/colapso de una subcategoría en el modal. */
const toggleSubcategoria = (subcategoria: string) => {
  setSubcategoriasAbiertas((prev) =>
    prev.includes(subcategoria)
      ? prev.filter((s) => s !== subcategoria) // cerrar
      : [...prev, subcategoria] // abrir
  );
};
    return (
    <div className="modal-overlay">
      <div className="modal-content">
        <div className="modal-header">
          <button onClick={onClose} className="btn-cerrar">✕</button>
          <h3 className="textos titulo-h3 ">Variables por Subcategoría</h3>

          <div className="seleccion-info">
            <span className="contador textos">
              {variablesSeleccionadas.length} de {variables.length} seleccionadas
            </span>
            {variables.length > 0 && (
              <button onClick={toggleTodasVariables} className="btn-todos textos">
                {variablesSeleccionadas.length === variables.length
                  ? "Deseleccionar"
                  : "Seleccionar"} todos
              </button>
            )}
          </div>
        </div>

        <div className="lista-subcategorias">
  {Object.entries(variablesPorSubcategoria).map(([subcategoria, vars]) => (
    <div key={subcategoria} className="subcategoria-bloque">
      <h4 
        className="subcategoria-titulo" 
        onClick={() => toggleSubcategoria(subcategoria)}
        style={{ cursor: "pointer" }}
      >
        {subcategoria} {subcategoriasAbiertas.includes(subcategoria) ? "▼" : "▶"}
      </h4>

      {subcategoriasAbiertas.includes(subcategoria) && (
        <ul className="lista-variables">
          {vars.map((variable) => (
            <li
              key={variable.id}
              className={variablesSeleccionadas.includes(variable.nombre) ? "seleccionado" : ""}
              onClick={() => toggleVariable(variable.nombre)}
              style={{ cursor: "pointer" }}
            >
              <input
                type="checkbox"
                checked={variablesSeleccionadas.includes(variable.nombre)}
                onClick={(e) => e.stopPropagation()}
                onChange={() => toggleVariable(variable.nombre)}
              />
              <span>{variable.nombre}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  ))}
        </div>
      </div>
    </div>
  );
};


export default VariablesModal;