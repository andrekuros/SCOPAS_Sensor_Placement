"""
Stoplight Chart Visualization - Figura 9 do Artigo MUSCAT

Este módulo implementa o "stoplight chart" usado no artigo MUSCAT para visualizar
quais combinações de sensores atendem aos requisitos:
- Verde: Atende ambos os requisitos (cobertura >95% e overlap >55%)
- Amarelo: Atende apenas um requisito
- Vermelho: Não atende nenhum requisito

Referência: Figura 9 do artigo MUSCAT
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import ListedColormap, LinearSegmentedColormap, LogNorm, Normalize, PowerNorm
from typing import List, Dict, Any, Tuple, Union
import plotly.graph_objects as go
import plotly.express as px


def plot_stoplight_chart_matplotlib(
    results_list: List[Dict[str, Any]],
    min_coverage: float = 0.95,
    min_overlap: float = 0.55,
    save_path: str = None,
    title: str = "Sensor Configuration Requirements Analysis"
) -> plt.Figure:
    """
    Gera stoplight chart usando Matplotlib (estilo Figura 9 do MUSCAT).
    
    Args:
        results_list: Lista de dicts com resultados de diferentes configurações.
                      Cada dict deve conter:
                      - 'config_name': str (ex: "4R+4RID")
                      - 'num_radars': int
                      - 'num_rids': int (ou outros tipos)
                      - 'Mc': float (coverage)
                      - 'overlap': float (overlap entre sensores)
        min_coverage: Requisito mínimo de cobertura (padrão: 0.95)
        min_overlap: Requisito mínimo de overlap (padrão: 0.55)
        save_path: Caminho para salvar a figura (opcional)
        title: Título do gráfico
        
    Returns:
        Figura matplotlib
        
    Exemplo:
        >>> results = [
        ...     {'config_name': '4R+4RID', 'Mc': 0.97, 'overlap': 0.60},
        ...     {'config_name': '5R+3RID', 'Mc': 0.97, 'overlap': 0.52},
        ...     {'config_name': '6R+2RID', 'Mc': 0.95, 'overlap': 0.48},
        ... ]
        >>> fig = plot_stoplight_chart_matplotlib(results)
        >>> plt.show()
    """
    # Preparar dados
    configs = []
    colors = []
    coverage_values = []
    overlap_values = []
    
    for result in results_list:
        config_name = result.get('config_name', 'Unknown')
        Mc = result.get('Mc', 0)
        overlap = result.get('overlap', result.get('avg_redundancy', 0))
        
        # Verificar requisitos
        meets_coverage = Mc >= min_coverage
        meets_overlap = overlap >= min_overlap
        
        # Determinar cor
        if meets_coverage and meets_overlap:
            color = 'green'  # Atende ambos
        elif meets_coverage or meets_overlap:
            color = 'yellow'  # Atende um
        else:
            color = 'red'  # Não atende nenhum
        
        configs.append(config_name)
        colors.append(color)
        coverage_values.append(Mc * 100)
        overlap_values.append(overlap * 100)
    
    # Criar figura
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Configurar eixos
    x = np.arange(len(configs))
    width = 0.35
    
    # Plotar barras de cobertura
    bars1 = ax.bar(x - width/2, coverage_values, width, 
                   label='Coverage (%)', alpha=0.8, color='skyblue', edgecolor='black')
    
    # Plotar barras de overlap
    bars2 = ax.bar(x + width/2, overlap_values, width,
                   label='Overlap (%)', alpha=0.8, color='lightcoral', edgecolor='black')
    
    # Adicionar linhas de requisitos
    ax.axhline(y=min_coverage*100, color='blue', linestyle='--', 
               linewidth=2, label=f'Min Coverage ({min_coverage*100:.0f}%)')
    ax.axhline(y=min_overlap*100, color='red', linestyle='--', 
               linewidth=2, label=f'Min Overlap ({min_overlap*100:.0f}%)')
    
    # Colorir fundo de acordo com status
    for i, (config, color) in enumerate(zip(configs, colors)):
        # Retângulo colorido no fundo
        ax.add_patch(plt.Rectangle((i-0.5, 0), 1, 100, 
                                   facecolor=color, alpha=0.15, zorder=0))
    
    # Adicionar valores sobre as barras
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax.annotate(f'{height:.1f}',
                       xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, 3),
                       textcoords="offset points",
                       ha='center', va='bottom', fontsize=9, fontweight='bold')
    
    # Configurar labels
    ax.set_xlabel('Sensor Configuration', fontsize=12, fontweight='bold')
    ax.set_ylabel('Percentage (%)', fontsize=12, fontweight='bold')
    ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
    ax.set_xticks(x)
    ax.set_xticklabels(configs, rotation=45, ha='right')
    ax.set_ylim(0, 105)
    ax.legend(loc='upper right', fontsize=10)
    ax.grid(axis='y', alpha=0.3, linestyle=':')
    
    # Adicionar legenda de cores
    green_patch = mpatches.Patch(color='green', alpha=0.3, label='✓ Meets All Requirements')
    yellow_patch = mpatches.Patch(color='yellow', alpha=0.3, label='⚠ Meets One Requirement')
    red_patch = mpatches.Patch(color='red', alpha=0.3, label='✗ Meets No Requirements')
    
    ax.legend(handles=[bars1, bars2, green_patch, yellow_patch, red_patch],
             loc='upper left', fontsize=9, framealpha=0.9)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"✅ Stoplight chart salvo em: {save_path}")
    
    return fig


def plot_stoplight_chart_plotly(
    results_list: List[Dict[str, Any]],
    min_coverage: float = 0.95,
    min_overlap: float = 0.55,
    save_path: str = None,
    title: str = "Sensor Configuration Requirements Analysis"
) -> go.Figure:
    """
    Gera stoplight chart interativo usando Plotly.
    
    Args:
        results_list: Lista de dicts com resultados de configurações
        min_coverage: Requisito mínimo de cobertura
        min_overlap: Requisito mínimo de overlap
        save_path: Caminho para salvar HTML interativo
        title: Título do gráfico
        
    Returns:
        Figura Plotly
    """
    # Preparar dados
    configs = []
    coverage_values = []
    overlap_values = []
    status_colors = []
    status_text = []
    
    for result in results_list:
        config_name = result.get('config_name', 'Unknown')
        Mc = result.get('Mc', 0)
        overlap = result.get('overlap', result.get('avg_redundancy', 0))
        
        # Verificar requisitos
        meets_coverage = Mc >= min_coverage
        meets_overlap = overlap >= min_overlap
        
        # Determinar status
        if meets_coverage and meets_overlap:
            status = '✓ Meets All'
            color = 'green'
        elif meets_coverage or meets_overlap:
            status = '⚠ Meets One'
            color = 'gold'
        else:
            status = '✗ Meets None'
            color = 'red'
        
        configs.append(config_name)
        coverage_values.append(Mc * 100)
        overlap_values.append(overlap * 100)
        status_colors.append(color)
        status_text.append(status)
    
    # Criar figura
    fig = go.Figure()
    
    # Adicionar barras de cobertura
    fig.add_trace(go.Bar(
        name='Coverage (%)',
        x=configs,
        y=coverage_values,
        marker_color='skyblue',
        marker_line_color='darkblue',
        marker_line_width=1.5,
        text=[f'{v:.1f}%' for v in coverage_values],
        textposition='outside',
        hovertemplate='<b>%{x}</b><br>Coverage: %{y:.2f}%<extra></extra>'
    ))
    
    # Adicionar barras de overlap
    fig.add_trace(go.Bar(
        name='Overlap (%)',
        x=configs,
        y=overlap_values,
        marker_color='lightcoral',
        marker_line_color='darkred',
        marker_line_width=1.5,
        text=[f'{v:.1f}%' for v in overlap_values],
        textposition='outside',
        hovertemplate='<b>%{x}</b><br>Overlap: %{y:.2f}%<extra></extra>'
    ))
    
    # Adicionar linhas de requisitos
    fig.add_hline(y=min_coverage*100, line_dash="dash", line_color="blue",
                  annotation_text=f"Min Coverage ({min_coverage*100:.0f}%)",
                  annotation_position="right")
    
    fig.add_hline(y=min_overlap*100, line_dash="dash", line_color="red",
                  annotation_text=f"Min Overlap ({min_overlap*100:.0f}%)",
                  annotation_position="right")
    
    # Adicionar retângulos coloridos no fundo (shapes)
    for i, (config, color) in enumerate(zip(configs, status_colors)):
        fig.add_shape(
            type="rect",
            x0=i-0.5, x1=i+0.5, y0=0, y1=105,
            fillcolor=color,
            opacity=0.1,
            layer="below",
            line_width=0
        )
    
    # Layout
    fig.update_layout(
        title={
            'text': title,
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 16, 'color': 'black', 'family': 'Arial, bold'}
        },
        xaxis_title="Sensor Configuration",
        yaxis_title="Percentage (%)",
        barmode='group',
        height=600,
        width=1200,
        font=dict(size=12),
        hovermode='x unified',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        yaxis=dict(range=[0, 105], gridcolor='lightgray'),
        plot_bgcolor='white'
    )
    
    if save_path:
        fig.write_html(save_path)
        print(f"✅ Stoplight chart interativo salvo em: {save_path}")
    
    return fig


def plot_requirements_matrix(
    results_list: List[Dict[str, Any]],
    min_coverage: float = 0.95,
    min_overlap: float = 0.55,
    save_path: str = None
) -> go.Figure:
    """
    Gera matriz de requisitos (scatter plot) mostrando coverage vs overlap.
    
    Cores:
    - Verde: Ambos requisitos atendidos
    - Amarelo: Um requisito atendido
    - Vermelho: Nenhum requisito atendido
    
    Args:
        results_list: Lista de configurações com métricas
        min_coverage: Requisito mínimo de cobertura
        min_overlap: Requisito mínimo de overlap
        save_path: Caminho para salvar HTML
        
    Returns:
        Figura Plotly
    """
    # Preparar dados
    configs = []
    coverage_values = []
    overlap_values = []
    colors = []
    sizes = []
    costs = []
    
    for result in results_list:
        config_name = result.get('config_name', 'Unknown')
        Mc = result.get('Mc', 0)
        overlap = result.get('overlap', result.get('avg_redundancy', 0))
        cost = result.get('total_cost', 0)
        
        # Determinar cor
        meets_coverage = Mc >= min_coverage
        meets_overlap = overlap >= min_overlap
        
        if meets_coverage and meets_overlap:
            color = 'green'
        elif meets_coverage or meets_overlap:
            color = 'gold'
        else:
            color = 'red'
        
        configs.append(config_name)
        coverage_values.append(Mc * 100)
        overlap_values.append(overlap * 100)
        colors.append(color)
        sizes.append(max(10, cost / 2))  # Tamanho proporcional ao custo
        costs.append(cost)
    
    # Criar scatter plot
    fig = go.Figure()
    
    # Adicionar pontos
    fig.add_trace(go.Scatter(
        x=coverage_values,
        y=overlap_values,
        mode='markers+text',
        marker=dict(
            size=sizes,
            color=colors,
            line=dict(color='black', width=2),
            opacity=0.7
        ),
        text=configs,
        textposition='top center',
        textfont=dict(size=10, color='black'),
        hovertemplate='<b>%{text}</b><br>' +
                      'Coverage: %{x:.2f}%<br>' +
                      'Overlap: %{y:.2f}%<br>' +
                      'Cost: %{customdata:.0f} UoM<extra></extra>',
        customdata=costs
    ))
    
    # Adicionar linhas de requisitos
    fig.add_vline(x=min_coverage*100, line_dash="dash", line_color="blue",
                  line_width=2,
                  annotation_text=f"Min Coverage ({min_coverage*100:.0f}%)",
                  annotation_position="top")
    
    fig.add_hline(y=min_overlap*100, line_dash="dash", line_color="red",
                  line_width=2,
                  annotation_text=f"Min Overlap ({min_overlap*100:.0f}%)",
                  annotation_position="right")
    
    # Adicionar regiões coloridas
    # Região verde (ambos requisitos atendidos)
    fig.add_shape(
        type="rect",
        x0=min_coverage*100, x1=100, y0=min_overlap*100, y1=100,
        fillcolor="green",
        opacity=0.1,
        layer="below",
        line_width=0
    )
    
    # Layout
    fig.update_layout(
        title="Requirements Matrix: Coverage vs Overlap",
        xaxis_title="Coverage (%)",
        yaxis_title="Overlap (%)",
        height=600,
        width=800,
        font=dict(size=12),
        plot_bgcolor='white',
        xaxis=dict(range=[80, 102], gridcolor='lightgray'),
        yaxis=dict(range=[40, 102], gridcolor='lightgray')
    )
    
    if save_path:
        fig.write_html(save_path)
        print(f"✅ Requirements matrix salva em: {save_path}")
    
    return fig


def create_stoplight_summary_table(
    results_list: List[Dict[str, Any]],
    min_coverage: float = 0.95,
    min_overlap: float = 0.55
) -> str:
    """
    Cria tabela de resumo em texto com status stoplight.
    
    Args:
        results_list: Lista de configurações
        min_coverage: Requisito de cobertura
        min_overlap: Requisito de overlap
        
    Returns:
        String com tabela formatada
    """
    # Header
    table = "\n" + "="*90 + "\n"
    table += "STOPLIGHT ANALYSIS - Configuration Requirements Summary\n"
    table += "="*90 + "\n"
    table += f"{'Config':<15} {'Cost':>8} {'Coverage':>10} {'Overlap':>10} {'Status':>10} {'Verdict':<20}\n"
    table += "-"*90 + "\n"
    
    # Linhas
    for result in results_list:
        config = result.get('config_name', 'Unknown')[:14]
        cost = result.get('total_cost', 0)
        Mc = result.get('Mc', 0)
        overlap = result.get('overlap', result.get('avg_redundancy', 0))
        
        # Status
        meets_coverage = Mc >= min_coverage
        meets_overlap = overlap >= min_overlap
        
        if meets_coverage and meets_overlap:
            status = '🟢 GREEN'
            verdict = '✓ Meets All'
        elif meets_coverage or meets_overlap:
            status = '🟡 YELLOW'
            verdict = '⚠ Meets One'
        else:
            status = '🔴 RED'
            verdict = '✗ Meets None'
        
        table += f"{config:<15} {cost:>8.0f} {Mc*100:>9.2f}% {overlap*100:>9.2f}% {status:>10} {verdict:<20}\n"
    
    table += "="*90 + "\n"
    table += f"Requirements: Coverage ≥ {min_coverage*100:.0f}%, Overlap ≥ {min_overlap*100:.0f}%\n"
    table += "="*90 + "\n"
    
    return table


def heatmap_colormaps(lut_size: int = 256):
    """
    Coverage / redundancy colormaps with a large LUT (default 256) to avoid
    visible banding from too few discrete colors.
    """
    cov_colors = [
        "#ffffff",
        "#e5f5e0",
        "#c7e9c0",
        "#a1d99b",
        "#74c476",
        "#41ab5d",
        "#238b45",
        "#005a32",
    ]
    red_colors = [
        "#f7fbff",
        "#deebf7",
        "#c6dbef",
        "#9ecae1",
        "#6baed6",
        "#3182bd",
        "#08519c",
    ]
    cmap_cov = LinearSegmentedColormap.from_list("coverage_smooth", cov_colors, N=lut_size)
    cmap_cov.set_bad(color="#f5f5f5", alpha=0.35)
    cmap_red = LinearSegmentedColormap.from_list("redundancy_smooth", red_colors, N=lut_size)
    cmap_red.set_bad(color="#f5f5f5", alpha=0.35)
    return cmap_cov, cmap_red


def upsample_scalar_field_2d(
    arr: np.ndarray,
    factor: int,
    *,
    order: int = 3,
    clip_0_1: bool = False,
) -> np.ndarray:
    """
    Upsample a 2D field for nicer heatmaps. NaN marks invalid/occupied cells and
    is preserved (nearest-neighbour mask) so buildings stay sharp while free
    space is interpolated smoothly (reduces voxel stair-steps).
    Prefer ``order=1`` (bilinear) for display to limit ringing; ``order=3`` is sharper but can overshoot.

    Requires SciPy (``ndimage.zoom``).
    """
    if factor <= 1:
        return arr
    try:
        from scipy.ndimage import zoom
    except ImportError as e:
        raise ImportError("upsample_scalar_field_2d requires scipy") from e
    raw = np.asarray(arr, dtype=np.float64)
    occ = np.isnan(raw)
    filled = np.where(occ, 0.0, raw)
    up = zoom(filled, factor, order=order)
    occ_up = zoom(occ.astype(np.float64), factor, order=0) >= 0.5
    up[occ_up] = np.nan
    if clip_0_1:
        fin = np.isfinite(up)
        up[fin] = np.clip(up[fin], 0.0, 1.0)
    return up


def prepare_detection_probability_display(
    p_map: np.ndarray,
    *,
    scale: str = "power",
    p_floor: float = 1e-3,
    power_gamma: float = 0.45,
) -> Tuple[np.ndarray, Union[LogNorm, Normalize, PowerNorm], str]:
    """
    Format network detection probability (0..1) for imshow.

    - **power** (default): ``PowerNorm`` with ``vmin=0``, ``vmax=1``. Mapped
      color index is ``(Pd)**gamma`` (matplotlib convention). **gamma < 1**
      **compresses** the high-Pd band (0.7–1.0 uses less of the colormap) so
      the falloff is visible instead of a huge flat dark-green disk and a cliff.
      **gamma > 1** does the opposite (more colormap for strong coverage).
      Pd==0 on free space is masked (NaN) so “no detection” uses ``set_bad``.
    - **log**: ``LogNorm`` — strong contrast at very low Pd (uses ``p_floor``).
    - **linear**: uniform in Pd (half the bar is 0.5–1.0 → easy “blob + step”).

    Occupied voxels (NaN) remain NaN.
    """
    raw = np.asarray(p_map, dtype=np.float64)
    display = raw.copy()
    occ = np.isnan(raw)
    display[occ] = np.nan
    free = ~occ
    scale = (scale or "power").lower()
    norm: Union[LogNorm, Normalize, PowerNorm]
    if scale == "power":
        if not (0.2 <= power_gamma <= 2.5):
            raise ValueError("power_gamma should be in [0.2, 2.5] for coverage")
        display[free & (raw <= 0.0)] = np.nan
        fin = free & (raw > 0.0)
        display[fin] = np.clip(display[fin], 0.0, 1.0)
        norm = PowerNorm(gamma=power_gamma, vmin=0.0, vmax=1.0)
        label = f"Detection probability (P to color, gamma={power_gamma:g})"
    elif scale == "log":
        if p_floor <= 0.0 or p_floor >= 1.0:
            raise ValueError("p_floor must be in (0, 1) for log coverage scale")
        display[free & (raw <= 0.0)] = np.nan
        tiny = free & (raw > 0.0) & (raw < p_floor)
        display[tiny] = p_floor
        norm = LogNorm(vmin=p_floor, vmax=1.0)
        label = "Detection probability (log scale)"
    elif scale == "linear":
        display[free & (raw < 0.0)] = np.nan
        norm = Normalize(vmin=0.0, vmax=1.0)
        label = "Detection probability"
    else:
        raise ValueError(f"Unknown scale={scale!r}; use 'power', 'log', or 'linear'")
    return display, norm, label


def prepare_redundancy_sum_display(
    r_map: np.ndarray,
    *,
    gamma: float = 0.5,
) -> Tuple[np.ndarray, PowerNorm, str]:
    """
    Sum-of-Pd redundancy: PowerNorm on [0, vmax]. gamma < 1 compresses large
    sums (less solid dark core), like coverage ``power`` with gamma < 1.
    """
    raw = np.asarray(r_map, dtype=np.float64)
    display = raw.copy()
    finite = np.isfinite(display)
    vmax = float(np.nanmax(display)) if finite.any() else 1.0
    if not np.isfinite(vmax) or vmax <= 0.0:
        vmax = 1.0
    norm = PowerNorm(gamma=gamma, vmin=0.0, vmax=vmax)
    label = f"Sensors detecting (Pd sum, gamma={gamma:g})"
    return display, norm, label


if __name__ == "__main__":
    # Exemplo de uso baseado na Tabela III do MUSCAT
    print("=== Teste de Stoplight Chart (Figura 9 MUSCAT) ===\n")
    
    # Dados de exemplo (baseados na Tabela III do artigo)
    results_example = [
        {
            'config_name': '4R+4RID',
            'num_radars': 4,
            'num_rids': 4,
            'Mc': 0.9716,
            'overlap': 0.60,
            'total_cost': 24,
            'CA': 0.25
        },
        {
            'config_name': '5R+3RID',
            'num_radars': 5,
            'num_rids': 3,
            'Mc': 0.9700,
            'overlap': 0.52,
            'total_cost': 28,
            'CA': 0.29
        },
        {
            'config_name': '6R+2RID',
            'num_radars': 6,
            'num_rids': 2,
            'Mc': 0.9503,
            'overlap': 0.48,
            'total_cost': 32,
            'CA': 0.34
        },
        {
            'config_name': '3R+5RID',
            'num_radars': 3,
            'num_rids': 5,
            'Mc': 0.9800,
            'overlap': 0.58,
            'total_cost': 20,
            'CA': 0.20
        },
        {
            'config_name': '7R+1RID',
            'num_radars': 7,
            'num_rids': 1,
            'Mc': 0.9200,
            'overlap': 0.42,
            'total_cost': 36,
            'CA': 0.39
        },
        {
            'config_name': '2R+2RID',
            'num_radars': 2,
            'num_rids': 2,
            'Mc': 0.8500,
            'overlap': 0.35,
            'total_cost': 12,
            'CA': 0.14
        }
    ]
    
    # Criar tabela de resumo
    print(create_stoplight_summary_table(results_example))
    
    # Gerar visualizações
    print("\n📊 Gerando visualizações...\n")
    
    # Matplotlib
    fig_mpl = plot_stoplight_chart_matplotlib(
        results_example,
        save_path="muscat_stoplight_matplotlib.png"
    )
    
    # Plotly
    fig_plotly = plot_stoplight_chart_plotly(
        results_example,
        save_path="muscat_stoplight_plotly.html"
    )
    
    # Requirements Matrix
    fig_matrix = plot_requirements_matrix(
        results_example,
        save_path="muscat_requirements_matrix.html"
    )
    
    print("\n✅ Visualizações geradas com sucesso!")
    print("   - muscat_stoplight_matplotlib.png")
    print("   - muscat_stoplight_plotly.html")
    print("   - muscat_requirements_matrix.html")

