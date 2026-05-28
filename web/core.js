// --- CONFIGURACIÓN GLOBAL Y ESTADO ---
export const ARCHIVOS_LISTA = ["elida.json", "magliano.json", "chañar.json", "serrano.json", "gomez.json", "villa rossi.json"];

export let charts = {};
export let rawData = null;
export let selectedModel = null;
export let fechaFiltro = "all";
export let seccionActual = "resumen";

export const TRADUCCION_DIAS = {
    'Mon': 'Lun', 'Tue': 'Mar', 'Wed': 'Mié', 'Thu': 'Jue', 'Fri': 'Vie', 'Sat': 'Sáb', 'Sun': 'Dom',
    'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles', 'Thursday': 'Jueves', 
    'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
};

export const MODEL_COLORS = { 
    'GFS': '#0212A5', 'OpenMeteo': '#FF5757', 'SMN_WRF': '#D6D306', 
    'MET_Norway': '#00CC96', 'CONSENSO': '#60a5fa' 
};

// Functión para configurar los valores por defecto de Chart.js de manera controlada
export function aplicarConfiguracionGlobalChart() {
    Chart.defaults.plugins.tooltip.position = 'nearest';
    Chart.defaults.plugins.tooltip.backgroundColor = '#1e293b';
    Chart.defaults.plugins.tooltip.titleColor = '#60a5fa';
    Chart.defaults.plugins.tooltip.bodyColor = '#f1f5f9';
    Chart.defaults.plugins.tooltip.borderColor = '#334155';
    Chart.defaults.plugins.tooltip.borderWidth = 1;
    Chart.defaults.plugins.tooltip.padding = 10;

    Chart.defaults.plugins.tooltip.callbacks.title = function(context) {
        if (!context || !context[0]) return '';
        
        let rawValue = context[0].label || '';
        if (!rawValue && context[0].raw && context[0].raw.x) {
            rawValue = context[0].raw.x;
        }
        
        if (!rawValue) return '';
        if (!rawValue.toString().includes('-') || !rawValue.toString().includes(':')) {
            return rawValue;
        }
        
        const parts = rawValue.toString().split(' ');
        if (parts.length < 2) return rawValue;
        
        const fecha = parts[0]; 
        const hora = parts[1];  
        const horaCorta = hora.substring(0, 5); 
        
        const d = new Date(fecha + "T12:00:00");
        const diasSemanas = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb'];
        
        if (isNaN(d.getTime())) return rawValue;
        
        return `${diasSemanas[d.getDay()]} ${d.getDate()} - ${horaCorta} hs`;
    };

    Chart.register(divisorDiasPlugin);
}

export function formatearTextoEnEspañol(texto) {
    if (!texto) return '';
    let str = texto.toString();
    
    Object.keys(TRADUCCION_DIAS).forEach(diaIngles => {
        const regex = new RegExp(`\\b${diaIngles}\\b`, 'g');
        str = str.replace(regex, TRADUCCION_DIAS[diaIngles]);
    });
    
    return str;
}

export const ClimaFormatter = {
    aHoraMinuto(fechaStr) {
        if (!fechaStr) return '';
        const fecha = new Date(fechaStr.replace(' ', 'T'));
        const horas = String(fecha.getHours()).padStart(2, '0');
        return `${horas}:00`;
    },

    aDiaCorto(fechaStr) {
        if (!fechaStr) return '';
        const fecha = new Date(fechaStr.replace(' ', 'T'));
        const dias = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb'];
        return `${dias[fecha.getDay()]} ${fecha.getDate()}`;
    },

    obtenerHoraPura(label) {
        if (label && label.includes(':')) {
            return parseInt(label.split(':')[0], 10);
        }
        return null;
    }
};

// --- PLUGIN: DIBUJO DE LÍNEAS EN LAS MEDIANOCHES (00:00) ---
export const divisorDiasPlugin = {
    id: 'divisorDias',
    afterDraw: (chart) => {
        const { ctx, chartArea: { top, bottom }, scales: { x } } = chart;
        if (!x || !chart.data || !chart.data.labels) return;

        const esHorario = chart.data.labels.some(l => l && l.toString().includes(':'));
        if (!esHorario) return;

        ctx.save();
        ctx.strokeStyle = '#475569';
        ctx.setLineDash([4, 4]);
        ctx.lineWidth = 1.5;

        chart.data.labels.forEach((label, index) => {
            if (label) {
                const str = label.toString();
                const match = str.match(/\s+(\d{2}):/);
                if (match && match[1] === '00') {
                    const xPos = x.getPixelForValue(index);
                    if (xPos >= x.left && xPos <= x.right) {
                        ctx.beginPath();
                        ctx.moveTo(xPos, top);
                        ctx.lineTo(xPos, bottom);
                        ctx.stroke();
                    }
                }
            }
        });
        ctx.restore();
    }
};

// --- CONFIGURACIÓN DINÁMICA DEL EJE X CON PRIORIDAD MANUAL ---
export function getDynamicXConfig(isFiltered) {
    return {
        // 🌟 Usamos funciones dinámicas para obligar al Canvas a romper la caché de líneas
        grid: isFiltered 
            ? {
                display: true,
                drawOnChartArea: true,
                color: 'rgba(156, 163, 175, 0.25)', 
                
                // 🚀 El secreto: Pasarlos como funciones ejecutables
                borderDash: () => [4, 4], // Para Chart.js v3 y v4 (Grilla interna)
                dash: () => [4, 4]         // Por seguridad estructural
              }
            : { 
                display: false, 
                drawOnChartArea: false 
              },
        ticks: {
            maxRotation: 0,
            minRotation: 0,
            autoSkip: false, 
            color: '#94a3b8',
            font: { size: 10, weight: '600' },
            callback: function(val, index) {
                const label = this.getLabelForValue(val);
                if (!label || !label.includes(' ')) return '';

                const partes = label.split(' ');
                const fechaStr = partes[0];
                const horaStr = partes[1];
                const hora = parseInt(horaStr.split(':')[0]);

                const diasSemanas = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb'];

                if (isFiltered) {
                    return (hora % 3 === 0) ? `${hora}:00` : '';
                }
                
                const minVisible = this.chart.scales.x.min;
                const maxVisible = this.chart.scales.x.max;
                const puntosEnPantalla = maxVisible - minVisible;

                if (hora === 0) {
                    const dt = new Date(fechaStr + "T12:00:00");
                    return `${diasSemanas[dt.getDay()]} ${dt.getDate()}`;
                }

                if (puntosEnPantalla > 120) {
                    return '';
                } 
                else if (puntosEnPantalla <= 120 && puntosEnPantalla > 48) {
                    return (hora === 12) ? '12:00' : '';
                } 
                else {
                    return (hora % 6 === 0) ? `${hora}:00` : '';
                }
            }
        }
    };
}

// --- CONFIGURACIÓN DE ZOOM NATIVO ---
export const zoomOptions = {
    pan: { enabled: true, mode: 'x' },
    zoom: {
        wheel: { enabled: true },
        pinch: { enabled: true },
        mode: 'x'
    }
};

// --- OPCIONES BASE PARA LOS GRÁFICOS ---
export const baseOptions = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
        mode: 'index',
        intersect: false,
    },
    scales: {
        x: {
            offset: false,
            ...getDynamicXConfig(false), 
            grid: {
                display: true,
                borderDash: [5, 5], 
                color: function(context) {
                    const labels = context.chart.data.labels;
                    if (!labels || !labels[context.index]) return 'transparent';
                    
                    const labelActual = labels[context.index];
                    const hora = ClimaFormatter.obtenerHoraPura(labelActual);

                    if (hora !== null) {
                        return hora % 3 === 0 ? 'rgba(255, 255, 255, 0.12)' : 'transparent';
                    }

                    return 'rgba(255, 255, 255, 0.12)';
                }
            },
            ticks: { 
                color: '#64748b', 
                font: { size: 10 },
                callback: function(val, index) {
                    const label = this.getLabelForValue(val);
                    const hora = ClimaFormatter.obtenerHoraPura(label);
                    
                    if (hora !== null) {
                        return hora % 3 === 0 ? label : '';
                    }
                    return label;
                }
            }
        },
        y: { 
            grid: { 
                display: true,
                borderDash: [], 
                color: 'rgba(255, 255, 255, 0.08)',
                drawBorder: false
            },
            ticks: { 
                color: '#64748b', 
                font: { size: 10 } 
            }
        }
    },
    plugins: {
        legend: { display: false },
        zoom: zoomOptions,
        divisorDias: divisorDiasPlugin
    }
};

// --- CORE LOGIC FUNCTIONS ---
export async function inicializarApp() {
    aplicarConfiguracionGlobalChart(); // Aplica los Tooltips y el plugin justo antes de iniciar

    const selectLote = document.getElementById('selector-lote');
    const infoLotes = await Promise.all(ARCHIVOS_LISTA.map(async f => {
        try {
            const r = await fetch(`data/${f}`);
            const j = await r.json();
            return { file: f, nombre: j.metadata.lote };
        } catch(e) { return null; }
    }));
    
    infoLotes.filter(l => l).forEach(l => {
        const opt = document.createElement('option');
        opt.value = l.file; opt.textContent = l.nombre;
        selectLote.appendChild(opt);
    });

    const ctxs = ['chart-diario', 'chart-horario', 'chart-temp-rocio', 'chart-delta', 'chart-humedad', 'chart-viento'];
    ctxs.forEach(id => {
        const key = id.replace('chart-', '').replace('-rocio', '');
        const type = id === 'chart-diario' || id === 'chart-horario' ? 'bar' : 'line';
        
        const optConfig = JSON.parse(JSON.stringify(baseOptions));
        
        optConfig.scales.x.ticks.callback = baseOptions.scales.x.ticks.callback;
        optConfig.plugins.zoom = zoomOptions;
        optConfig.plugins.divisorDias = divisorDiasPlugin;

        if (id === 'chart-diario') optConfig.scales.x.offset = true;

        charts[key] = new Chart(document.getElementById(id), { 
            type, 
            data: { labels: [], datasets: [] }, 
            options: optConfig
        });
    });

    cambiarLote(selectLote.value);
}

export async function cambiarLote(archivo) {
    const res = await fetch(`data/${archivo}`);
    rawData = await res.json();
    poblarSelectorFechas();
    actualizarPantalla();
}

export function poblarSelectorFechas() {
    const select = document.getElementById('selector-fecha');
    select.innerHTML = '<option value="all">Próximos 7 días</option>';
    const mKey = Object.keys(rawData.horario)[0];
    const diasUnicos = [...new Set(rawData.horario[mKey].map(p => p.x.split(' ')[0]))];
    diasUnicos.forEach(f => {
        const d = new Date(f + "T12:00:00");
        const dias = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb'];
        const opt = document.createElement('option');
        opt.value = f; opt.innerText = `${dias[d.getDay()]} ${d.getDate()}`;
        select.appendChild(opt);
    });
}

export function actualizarPantalla() {
    document.getElementById('sec-resumen').style.display = (seccionActual === 'resumen') ? 'grid' : 'none';
    document.getElementById('sec-aire').style.display = (seccionActual !== 'resumen') ? 'block' : 'none';

    if (seccionActual === "resumen") {
        renderizarResumen();
    } else {
        selectedModel = (seccionActual === 'prueba') ? 'CONSENSO' : (selectedModel || 'OpenMeteo');
        document.getElementById('model-selector-container').style.display = (seccionActual === 'prueba') ? 'none' : 'flex';
        generarSelectorModelos();
        renderizarClima();
    }
    document.getElementById('footer-sync').innerText = `Sync: ${rawData.metadata.actualizado} | Lote: ${rawData.metadata.lote}`;
}

export function renderizarResumen() {
    charts.diario.data.labels = rawData.diario.labels.map(l => formatearTextoEnEspañol(l));
    charts.diario.data.datasets = [{ 
        label: 'Lluvia (mm)', 
        data: rawData.diario.data, 
        backgroundColor: '#3b82f6', 
        borderRadius: 5 
    }];

    charts.diario.options.scales.x = {
        type: 'category',
        ticks: { color: '#94a3b8', maxRotation: 0, minRotation: 0, autoSkip: true }
    };

    if (!charts.diario.options.plugins) charts.diario.options.plugins = {};
    charts.diario.options.plugins.tooltip = {
        ...charts.diario.options.plugins.tooltip,
        callbacks: {
            title: function(context) {
                if (!context || !context[0]) return '';
                return context[0].label || '';
            }
        }
    };

    charts.diario.update();

    const modelos = Object.keys(rawData.horario).filter(m => m !== 'CONSENSO');
    const dRef = fechaFiltro === "all" 
        ? rawData.horario['OpenMeteo'] 
        : rawData.horario['OpenMeteo'].filter(p => p.x.startsWith(fechaFiltro));

    charts.horario.data.labels = dRef.map(p => p.x);

    charts.horario.data.datasets = modelos.map(m => {
        const datosBrutos = fechaFiltro === "all" 
            ? rawData.horario[m] 
            : rawData.horario[m].filter(p => p.x.startsWith(fechaFiltro));

        return {
            label: m,
            backgroundColor: MODEL_COLORS[m],
            data: dRef.map(ref => {
                const punto = datosBrutos.find(p => p.x === ref.x);
                return punto ? punto.y : 0;
            })
        };
    });

    charts.horario.options.scales.x = {
        ...charts.horario.options.scales.x,
        ...getDynamicXConfig(fechaFiltro !== "all")
    };
    charts.horario.update();
    actualizarKPIs(dRef);
}

export function renderizarClima() {
    const d = fechaFiltro === "all" 
        ? rawData.horario[selectedModel] 
        : rawData.horario[selectedModel].filter(p => p.x.startsWith(fechaFiltro));
    
    const datasetBase = (label, data, color, fill = false) => ({
        label, data, borderColor: color, backgroundColor: color + '22', fill, tension: 0.2, pointRadius: 0
    });

    const esVistaUnDia = fechaFiltro !== "all";
    const configDinamica = getDynamicXConfig(esVistaUnDia);

    ['temp', 'delta', 'humedad', 'viento'].forEach(key => {
        charts[key].data.labels = d.map(p => p.x);

        if(key === 'temp') {
            charts[key].data.datasets = [datasetBase('Temp', d.map(p => p.temp), '#ef4444'), datasetBase('Rocío', d.map(p => p.rocio), '#06b6d4')];
        } else if(key === 'delta') {
            charts[key].data.datasets = [
                datasetBase('Delta', d.map(p => (p.temp - p.rocio).toFixed(1)), '#f472b6', true),
                { ...datasetBase('Umbral Mín (8)', Array(d.length).fill(8), '#eab30866'), borderDash: [8, 1] },
                { ...datasetBase('Umbral Máx (12)', Array(d.length).fill(12), '#eab30866'), borderDash: [8, 1] },
                { ...datasetBase('Óptimo Mín (9)', Array(d.length).fill(9), '#22c55e66'), borderDash: [8, 1] },
                { ...datasetBase('Óptimo Máx (11)', Array(d.length).fill(11), '#22c55e66'), borderDash: [8, 1] }
            ];
        } else if(key === 'humedad') {
            charts[key].data.datasets = [datasetBase('Hum %', d.map(p => p.hum), '#10b981')];
        } else if(key === 'viento') {
            charts[key].data.datasets = [datasetBase('Viento m/s', d.map(p => p.viento), '#8b5cf6')];
        }

        const tipoEjeOriginal = charts[key].options.scales.x?.type || 'category';

        // 🌟 ASIGNACIÓN LIMPIA: Seteamos todo en el árbol de opciones principal
        charts[key].options.scales.x = {
            type: tipoEjeOriginal,
            ...configDinamica
        };

        // 🌟 ELIMINADO: Quitamos por completo el bloque "charts[key].scales.x.options.grid = ..." 
        // que corrompía el copiado del array borderDash.

        // Forzamos un update completo para que vuelva a compilar el árbol de opciones de cero
        charts[key].update(); 
    });
    actualizarKPIs(d);
}

export function actualizarKPIs(datos) {
    if (!datos || !datos.length) return;
    const temps = datos.map(p => p.temp).filter(v => v !== undefined), vientos = datos.map(p => p.viento).filter(v => v !== undefined);
    const hums = datos.map(p => p.hum).filter(v => v !== undefined), deltas = datos.map(p => p.temp - p.rocio).filter(v => !isNaN(v));
    
    document.getElementById('kpi-temp-max').innerText = temps.length ? Math.max(...temps).toFixed(1) : '--';
    document.getElementById('kpi-temp-min').innerText = temps.length ? Math.min(...temps).toFixed(1) : '--';
    document.getElementById('kpi-hum-max').innerText = hums.length ? Math.max(...hums).toFixed(0) : '--';
    document.getElementById('kpi-viento-max').innerText = vientos.length ? Math.max(...vientos).toFixed(1) : '--';
    document.getElementById('kpi-delta-min').innerText = deltas.length ? Math.min(...deltas).toFixed(1) : '--';
}

export function generarSelectorModelos() {
    const container = document.getElementById('model-selector-container');
    container.innerHTML = '';
    Object.keys(rawData.horario).filter(m => m !== 'CONSENSO').forEach(m => {
        const btn = document.createElement('button');
        btn.innerText = m;
        btn.className = `btn-model ${m === selectedModel ? 'btn-model-active' : ''}`;
        btn.style.borderLeft = `4px solid ${MODEL_COLORS[m]}`;
        btn.onclick = () => { selectedModel = m; actualizarPantalla(); };
        container.appendChild(btn);
    });
}

export function filtrarPorFecha(val) { 
    fechaFiltro = val; 
    actualizarPantalla(); 
    setTimeout(resetAllZooms, 50); 
}

export function verSeccion(sec) {
    seccionActual = sec;
    ['resumen', 'aire', 'prueba'].forEach(t => {
        const el = document.getElementById(`tab-${t}`);
        if(el) el.className = t === sec ? 'btn-tab btn-active flex-1 px-4 py-3 rounded-xl text-[10px] font-800 uppercase tracking-widest' : 'btn-tab bg-slate-800 text-slate-500 flex-1 px-4 py-3 rounded-xl text-[10px] font-800 uppercase tracking-widest';
    });
    actualizarPantalla();
}

export function resetAllZooms() { 
    Object.values(charts).forEach(c => { if(c.resetZoom) c.resetZoom(); }); 
}