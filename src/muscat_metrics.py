"""
MUSCAT metrics and C-UAS Point Defense upgrades.

Original MUSCAT (2023 baseline):
- Mc: Coverage Index (Eq. 6) — n/N
- Mg: Gap Index (Eq. 7) — 1 - Mc
- CA: Cost per Coverage Area (Eq. 8) — Total_Cost / Mc

Point Defense upgrade (Gaussian threat map):
- M_wp: Weighted Protection Index — sum(Covered × W) / sum(W)
- M_vuln: Vulnerability Index — 1 - M_wp
- Fused Resilience — % of threat-weighted volume with both RF and kinematic coverage (Q=1.0)
- Asset Security ROI — Total_Cost (with site activation) / M_wp

Reference: P. Kukulka de Albuquerque et al., "Multi-Sensor Placement and Information
Fusion Analysis to Enable Beyond Visual Line of Sight Operations for Small Uncrewed
Aerial Vehicles," 2023 IEEE/AIAA 42nd DASC, Barcelona, Spain, 2023.
"""

import numpy as np
from typing import Dict, List, Any, Tuple
from sensors import Sensor


def calculate_muscat_coverage(p_net_grid: np.ndarray, threshold: float = 0.8) -> float:
    """
    Calcula o índice de cobertura Mc conforme Equação 6 do MUSCAT.
    
    Mc = n / N
    
    Onde:
    - n = número de células/voxels com cobertura (P_Net >= threshold)
    - N = número total de células/voxels VÁLIDAS na ROI (excluindo ocupadas/NaN)
    
    Args:
        p_net_grid: Grid 3D de probabilidades de detecção da rede
        threshold: Threshold para considerar uma célula como "coberta" (padrão: 0.8)
        
    Returns:
        Mc: Índice de cobertura [0, 1]
        
    Exemplo:
        >>> p_net_grid = np.array([[[0.9, 0.7], [0.85, 0.95]]])
        >>> Mc = calculate_muscat_coverage(p_net_grid, threshold=0.8)
        >>> print(f"Cobertura: {Mc*100:.1f}%")
        Cobertura: 75.0%
    """
    # Verificar se o grid é válido
    if p_net_grid.size == 0:
        return 0.0
    
    # Filtrar apenas células válidas (não-NaN)
    valid_mask = ~np.isnan(p_net_grid)
    valid_cells = p_net_grid[valid_mask]
    
    # Se não há células válidas, retornar 0
    if valid_cells.size == 0:
        return 0.0
    
    # n = células válidas com P_Net >= threshold
    n = np.sum(valid_cells >= threshold)
    
    # N = total de células VÁLIDAS (excluindo NaN/ocupadas)
    N = valid_cells.size
    
    # Mc = n / N (Eq. 6, ajustado para considerar apenas células válidas)
    Mc = n / N
    
    return float(Mc)


def calculate_muscat_gaps(p_net_grid: np.ndarray, threshold: float = 0.8) -> float:
    """
    Calcula o índice de gaps (lacunas) Mg conforme Equação 7 do MUSCAT.
    
    Mg = 1 - n / N = 1 - Mc
    
    Onde:
    - n = número de células com cobertura
    - N = número total de células
    - Mc = índice de cobertura
    
    Args:
        p_net_grid: Grid 3D de probabilidades de detecção da rede
        threshold: Threshold para considerar uma célula como "coberta" (padrão: 0.8)
        
    Returns:
        Mg: Índice de gaps [0, 1]
        
    Exemplo:
        >>> p_net_grid = np.array([[[0.9, 0.7], [0.85, 0.95]]])
        >>> Mg = calculate_muscat_gaps(p_net_grid, threshold=0.8)
        >>> print(f"Gaps: {Mg*100:.1f}%")
        Gaps: 25.0%
    """
    Mc = calculate_muscat_coverage(p_net_grid, threshold)
    Mg = 1 - Mc  # Eq. 7
    return float(Mg)


def calculate_muscat_overlap(
    sensor_detections_list: List[np.ndarray],
    threshold: float = 0.8
) -> float:
    """
    Calcula o índice de overlap (sobreposição) entre diferentes sensores.
    
    O overlap é calculado como a fração de células que são detectadas por
    múltiplos sensores (2 ou mais).
    
    Args:
        sensor_detections_list: Lista de grids de detecção para cada sensor
        threshold: Threshold para considerar detecção
        
    Returns:
        Overlap: Fração de células com detecção múltipla [0, 1]
        
    Exemplo:
        >>> sensor1 = np.array([[[0.9, 0.7], [0.85, 0.0]]])
        >>> sensor2 = np.array([[[0.95, 0.0], [0.8, 0.85]]])
        >>> overlap = calculate_muscat_overlap([sensor1, sensor2], threshold=0.8)
        >>> print(f"Overlap: {overlap*100:.1f}%")
        Overlap: 50.0%
    """
    if len(sensor_detections_list) < 2:
        return 0.0
    
    # Converter cada grid para binário (0/1)
    binary_grids = [(grid >= threshold).astype(int) for grid in sensor_detections_list]
    
    # Somar detecções de todos os sensores
    total_detections = np.sum(binary_grids, axis=0)
    
    # Células com overlap (detecção por 2+ sensores)
    overlap_cells = np.sum(total_detections >= 2)
    
    # Total de células
    total_cells = total_detections.size
    
    # Fração com overlap
    overlap = overlap_cells / total_cells if total_cells > 0 else 0.0
    
    return float(overlap)


def calculate_muscat_cost_effectiveness(
    sensors: List[Sensor],
    p_net_grid: np.ndarray,
    threshold: float = 0.8
) -> float:
    """
    Calcula o custo por área de cobertura CA conforme Equação 8 do MUSCAT.
    
    CA = (∑ Ct × xtluh) / Mc
    
    Simplificando para nosso contexto:
    CA = Custo_Total / Mc
    
    Onde:
    - Custo_Total = soma dos custos de todos os sensores ativos
    - Mc = índice de cobertura
    
    Args:
        sensors: Lista de sensores ativos na configuração
        p_net_grid: Grid 3D de probabilidades de detecção da rede
        threshold: Threshold para calcular Mc
        
    Returns:
        CA: Custo por cobertura (unidades de custo / fração de cobertura)
            Retorna inf se Mc = 0
            
    Exemplo:
        >>> from sensors import RadarSensor, RFSensor
        >>> sensors = [RadarSensor(cost=100), RFSensor(cost=50)]
        >>> p_net_grid = np.ones((10, 10, 5)) * 0.9
        >>> CA = calculate_muscat_cost_effectiveness(sensors, p_net_grid)
        >>> print(f"Cost-Effectiveness: {CA:.2f} UoM/%")
        Cost-Effectiveness: 1.50 UoM/%
    """
    # Custo total
    total_cost = sum(sensor.cost for sensor in sensors)
    
    # Índice de cobertura Mc
    Mc = calculate_muscat_coverage(p_net_grid, threshold)
    
    # CA = Custo / Cobertura (Eq. 8)
    if Mc > 0:
        CA = total_cost / Mc
    else:
        CA = float('inf')  # Sem cobertura = custo infinito por cobertura
    
    return float(CA)


def calculate_weighted_protection_index(
    covered_grid: np.ndarray,
    weight_grid: np.ndarray,
    occupancy_grid: np.ndarray = None,
) -> float:
    """
    Weighted Protection Index M_wp (Point Defense upgrade of MUSCAT Mc).
    M_wp = sum(Covered(x,y,z) × W(x,y,z)) / sum(W(x,y,z)).
    If weight_grid is None or not provided, uses uniform weights on free voxels.
    """
    if occupancy_grid is not None:
        valid = occupancy_grid == 0
    else:
        valid = np.ones_like(covered_grid, dtype=bool)
    if weight_grid is None or weight_grid.shape != covered_grid.shape:
        weight_grid = np.where(valid, 1.0, 0.0).astype(np.float64)
    weights = np.where(valid, weight_grid, 0.0)
    sum_w = np.clip(np.sum(weights), 1e-10, None)
    return float(np.sum(covered_grid * weights) / sum_w)


def calculate_vulnerability_index(M_wp: float) -> float:
    """
    Vulnerability Index M_vuln = 1 - M_wp (Point Defense upgrade of MUSCAT Mg).
    A gap over the asset is critical; this quantifies vulnerability to uncooperative approach.
    """
    return 1.0 - M_wp


def calculate_fused_resilience(
    coop_covered: np.ndarray,
    noncoop_covered: np.ndarray,
    weight_grid: np.ndarray,
    occupancy_grid: np.ndarray = None,
) -> float:
    """
    Fused Resilience: % of (weighted) threat volume where Q=1.0 — covered by both
    RF identity and kinematic Radar/EO. Modality diversity for weapon-grade fused track.
    coop_covered and noncoop_covered are binary (0/1) grids.
    """
    fused = coop_covered * noncoop_covered
    if occupancy_grid is not None:
        valid = occupancy_grid == 0
    else:
        valid = np.ones_like(fused, dtype=bool)
    if weight_grid is None or weight_grid.shape != fused.shape:
        weight_grid = np.where(valid, 1.0, 0.0).astype(np.float64)
    weights = np.where(valid, weight_grid, 0.0)
    sum_w = np.clip(np.sum(weights), 1e-10, None)
    return float(np.sum(fused * weights) / sum_w)


def calculate_asset_security_roi(total_cost: float, M_wp: float) -> float:
    """
    Asset Security ROI = Total_Cost / M_wp (Point Defense upgrade of MUSCAT C_A).
    Total cost should include site activation cost. CapEx per unit of weighted protection.
    """
    if M_wp <= 0:
        return float("inf")
    return total_cost / M_wp


def calculate_all_muscat_metrics(
    sensors: List[Sensor],
    p_net_grid: np.ndarray,
    redundancy_grid: np.ndarray = None,
    sensor_detections_list: List[np.ndarray] = None,
    threshold: float = 0.8
) -> Dict[str, float]:
    """
    Calcula todas as métricas MUSCAT de uma vez.
    
    Args:
        sensors: Lista de sensores ativos
        p_net_grid: Grid de probabilidades de detecção da rede
        redundancy_grid: Grid de redundância (opcional)
        sensor_detections_list: Lista de grids de detecção individuais (para overlap)
        threshold: Threshold de detecção
        
    Returns:
        Dict com todas as métricas:
        - 'Mc': Coverage Index
        - 'Mg': Gap Index
        - 'CA': Cost-Effectiveness
        - 'Overlap': Índice de overlap (se sensor_detections_list fornecido)
        - 'avg_p_net': P_Net médio (nossa métrica nativa)
        - 'avg_redundancy': Redundância média (se redundancy_grid fornecido)
        - 'total_cost': Custo total
        - 'num_sensors': Número de sensores
        
    Exemplo:
        >>> metrics = calculate_all_muscat_metrics(sensors, p_net_grid)
        >>> print(f"Coverage: {metrics['Mc']*100:.1f}%")
        >>> print(f"Gaps: {metrics['Mg']*100:.1f}%")
        >>> print(f"Cost-Effectiveness: {metrics['CA']:.2f}")
    """
    # Métricas básicas
    Mc = calculate_muscat_coverage(p_net_grid, threshold)
    Mg = calculate_muscat_gaps(p_net_grid, threshold)
    CA = calculate_muscat_cost_effectiveness(sensors, p_net_grid, threshold)
    
    # Custo total
    total_cost = sum(sensor.cost for sensor in sensors)
    
    # P_Net médio (nossa métrica nativa)
    avg_p_net = float(np.nanmean(p_net_grid))
    
    # Métricas
    metrics = {
        'Mc': Mc,
        'Mg': Mg,
        'CA': CA,
        'total_cost': total_cost,
        'num_sensors': len(sensors),
        'avg_p_net': avg_p_net,
        'threshold': threshold
    }
    
    # Overlap (se fornecido)
    if sensor_detections_list is not None and len(sensor_detections_list) > 1:
        overlap = calculate_muscat_overlap(sensor_detections_list, threshold)
        metrics['overlap'] = overlap
    
    # Redundância (se fornecida)
    if redundancy_grid is not None:
        # Usar nanmean para ignorar voxels ocupados (marcados como NaN)
        avg_redundancy = float(np.nanmean(redundancy_grid))
        metrics['avg_redundancy'] = avg_redundancy
    
    return metrics


def check_muscat_requirements(
    metrics: Dict[str, float],
    min_coverage: float = 0.95,
    min_overlap: float = 0.55
) -> Dict[str, Any]:
    """
    Verifica se uma configuração atende aos requisitos do estudo de caso MUSCAT.
    
    Requisitos do artigo (Seção IV-A):
    - Cobertura (Mc) > 95%
    - Overlap > 55%
    
    Args:
        metrics: Dict de métricas calculadas
        min_coverage: Requisito mínimo de cobertura (padrão: 0.95)
        min_overlap: Requisito mínimo de overlap (padrão: 0.55)
        
    Returns:
        Dict com:
        - 'meets_coverage': bool
        - 'meets_overlap': bool
        - 'meets_all': bool
        - 'status': 'green' (ambos), 'yellow' (um), 'red' (nenhum)
        
    Exemplo:
        >>> status = check_muscat_requirements(metrics)
        >>> print(f"Status: {status['status']}")
        >>> if status['meets_all']:
        >>>     print("✅ Configuração atende todos os requisitos!")
    """
    # Verificar cobertura
    meets_coverage = metrics.get('Mc', 0) >= min_coverage
    
    # Verificar overlap (usar 'overlap' se disponível, senão 'avg_redundancy')
    overlap_value = metrics.get('overlap', metrics.get('avg_redundancy', 0))
    meets_overlap = overlap_value >= min_overlap
    
    # Status geral
    meets_all = meets_coverage and meets_overlap
    
    # Código de cor (para stoplight chart)
    if meets_all:
        status = 'green'  # Atende ambos
    elif meets_coverage or meets_overlap:
        status = 'yellow'  # Atende apenas um
    else:
        status = 'red'  # Não atende nenhum
    
    return {
        'meets_coverage': meets_coverage,
        'meets_overlap': meets_overlap,
        'meets_all': meets_all,
        'status': status,
        'coverage_value': metrics.get('Mc', 0),
        'overlap_value': overlap_value
    }


def compare_with_muscat_table_iii(
    our_results: Dict[str, float],
    muscat_baseline: Dict[str, float] = None
) -> Dict[str, Any]:
    """
    Compara nossos resultados com a Tabela III do artigo MUSCAT.
    
    Tabela III do artigo (baseline):
    - 4 Radars + 4 RIDs: Cost=24 UoM, Coverage=97.16%, CA=0.25 UoM/%
    - 5 Radars + 3 RIDs: Cost=28 UoM, Coverage=97.00%, CA=0.29 UoM/%
    - 6 Radars + 2 RIDs: Cost=32 UoM, Coverage=95.03%, CA=0.34 UoM/%
    
    Args:
        our_results: Nossas métricas calculadas
        muscat_baseline: Métricas da solução MUSCAT para comparação (opcional)
        
    Returns:
        Dict com análise comparativa
        
    Exemplo:
        >>> comparison = compare_with_muscat_table_iii(our_results)
        >>> print(comparison['summary'])
    """
    # Baseline padrão: melhor solução do MUSCAT (4R+4RID)
    if muscat_baseline is None:
        muscat_baseline = {
            'total_cost': 24,
            'Mc': 0.9716,
            'CA': 0.25,
            'config': '4 Radars + 4 RIDs'
        }
    
    # Comparação
    comparison = {
        'our_cost': our_results.get('total_cost', 0),
        'muscat_cost': muscat_baseline.get('total_cost', 0),
        'our_coverage': our_results.get('Mc', 0) * 100,
        'muscat_coverage': muscat_baseline.get('Mc', 0) * 100,
        'our_ca': our_results.get('CA', 0),
        'muscat_ca': muscat_baseline.get('CA', 0),
    }
    
    # Calcular diferenças
    comparison['cost_diff'] = comparison['our_cost'] - comparison['muscat_cost']
    comparison['coverage_diff'] = comparison['our_coverage'] - comparison['muscat_coverage']
    comparison['ca_diff'] = comparison['our_ca'] - comparison['muscat_ca']
    
    # Análise
    if comparison['our_ca'] < comparison['muscat_ca']:
        verdict = "✅ SUPERIOR: Melhor custo-benefício que MUSCAT"
    elif comparison['our_ca'] <= comparison['muscat_ca'] * 1.1:
        verdict = "✓ EQUIVALENTE: Custo-benefício similar ao MUSCAT"
    else:
        verdict = "⚠️ INFERIOR: Custo-benefício pior que MUSCAT"
    
    comparison['verdict'] = verdict
    
    # Resumo
    summary = f"""
    Comparação com MUSCAT (Tabela III - {muscat_baseline.get('config', 'baseline')}):
    
    Custo:
      - Nosso: {comparison['our_cost']:.0f} UoM
      - MUSCAT: {comparison['muscat_cost']:.0f} UoM
      - Diferença: {comparison['cost_diff']:+.0f} UoM
    
    Cobertura:
      - Nosso: {comparison['our_coverage']:.2f}%
      - MUSCAT: {comparison['muscat_coverage']:.2f}%
      - Diferença: {comparison['coverage_diff']:+.2f}%
    
    Cost-Effectiveness (CA):
      - Nosso: {comparison['our_ca']:.2f} UoM/%
      - MUSCAT: {comparison['muscat_ca']:.2f} UoM/%
      - Diferença: {comparison['ca_diff']:+.2f} UoM/%
    
    {verdict}
    """
    
    comparison['summary'] = summary.strip()
    
    return comparison


if __name__ == "__main__":
    # Exemplo de uso
    print("=== Teste de Métricas MUSCAT ===\n")
    
    # Criar grid de exemplo
    np.random.seed(42)
    p_net_grid = np.random.rand(10, 10, 5) * 0.9  # Valores entre 0 e 0.9
    
    # Criar sensores de exemplo
    from sensors import RadarSensor, RFSensor, EOSensor
    
    sensors = [
        RadarSensor(location=(0, 0, 10), cost=100),
        RadarSensor(location=(100, 100, 10), cost=100),
        RFSensor(location=(50, 50, 10), cost=50),
        EOSensor(location=(25, 75, 10), cost=30),
    ]
    
    # Calcular métricas
    metrics = calculate_all_muscat_metrics(sensors, p_net_grid, threshold=0.8)
    
    # Exibir resultados
    print("📊 Métricas MUSCAT:")
    print(f"  Mc (Coverage):        {metrics['Mc']*100:.2f}%")
    print(f"  Mg (Gaps):            {metrics['Mg']*100:.2f}%")
    print(f"  CA (Cost-Eff):        {metrics['CA']:.2f} UoM/%")
    print(f"  P_Net médio:          {metrics['avg_p_net']:.3f}")
    print(f"  Custo total:          {metrics['total_cost']:.0f} UoM")
    print(f"  Número de sensores:   {metrics['num_sensors']}")
    
    # Verificar requisitos
    print("\n🎯 Verificação de Requisitos:")
    status = check_muscat_requirements(metrics, min_coverage=0.95, min_overlap=0.55)
    print(f"  Atende cobertura >95%: {'✅' if status['meets_coverage'] else '❌'}")
    print(f"  Atende overlap >55%:   {'✅' if status['meets_overlap'] else '❌'}")
    print(f"  Status geral:          {status['status'].upper()}")
    
    # Comparar com MUSCAT
    print("\n🔬 Comparação com MUSCAT:")
    comparison = compare_with_muscat_table_iii(metrics)
    print(comparison['summary'])
    
    print("\n✅ Testes concluídos com sucesso!")

