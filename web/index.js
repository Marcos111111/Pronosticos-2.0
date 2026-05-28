// 1. Importás todo desde 'core.js' (agregando resetAllZooms)
import { inicializarApp, filtrarPorFecha, verSeccion, cambiarLote, resetAllZooms } from './core.js';

// 2. Inicialización
window.onload = inicializarApp;

// 3. Exponer al HTML
window.filtrarPorFecha = filtrarPorFecha;
window.verSeccion = verSeccion;
window.cambiarLote = cambiarLote;
window.resetAllZooms = resetAllZooms; // <--- Clave para que el botón de Reset funcione