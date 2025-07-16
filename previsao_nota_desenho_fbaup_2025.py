from typing import List, Dict, Tuple, Union
import random
import statistics
import heapq

PARAMS = {
    'correlacao': 0.1,
    'desvio_interna': 1.1,
    'vagas': 25,
    'candidatos': 350,
    'min_candidatos': 290,
    'max_candidatos': 375,
    'simulacoes': 1000,
    'media_interna_base': 16.4,
    'especulacao_variacao_media_interna': 0,
    'gda_probability': 0.4,
    'hca_probability': 0.4,
    'both_probability': 0.2,
    'exame_desenho_1f_2025': {  # https://www.portugal.gov.pt/download-ficheiros/ficheiro.aspx?v=%3D%3DBQAAAB%2BLCAAAAAAABAAzNDE1MgYAwRsqVQUAAAA%3D
        'total': 6527,
        # "10.0": 454,
        # "11.0": 474,
        # "12.0": 549,
        # "13.0": 606,
        # "14.0": 653,
        "15.0": 681,
        "16.0": 574,
        "17.0": 555,
        "18.0": 438,
        "19.0": 287,
        "20.0": 102
    },
    'exame_hca_1f_2025': {
        'total': 6408,
        # "10.0": 582,
        # "11.0": 606,
        # "12.0": 722,
        # "13.0": 669,
        # "14.0": 665,
        "15.0": 538,
        "16.0": 473,
        "17.0": 345,
        "18.0": 197,
        "19.0": 109,
        "20.0": 24
    },
    'exame_gda_1f_2024': {  # https://www.dge.mec.pt/sites/default/files/JNE/enes_hmlg2024_f1_distrib.pdf
        'total': 8011,
        # "9.5": 259,
        # "10.0": 158,
        # "10.5": 259,
        # "11.0": 160,
        # "11.5": 226,
        # "12.0": 136,
        # "12.5": 257,
        # "13.0": 160,
        # "13.5": 287,
        # "14.0": 153,
        # "14.5": 272,
        "15.0": 152,
        "15.5": 290,
        "16.0": 166,
        "16.5": 315,
        "17.0": 162,
        "17.5": 229,
        "18.0": 108,
        "18.5": 214,
        "19.0": 186,
        "19.5": 390,
        "20.0": 176
    }
}


def calcular_media_fbaup_desenho_2025(interna: float, desenho_a: float, gda_ou_hca: float) -> float:
    return interna * 0.5 + desenho_a * 0.3 + gda_ou_hca * 0.2  # https://www.dges.gov.pt/guias/detcursopi.asp?codc=8399&code=5402


def amostrar_lista(distribuicao: Dict[str, Union[int, float]]) -> List[float]:
    lista: List[float] = []
    for nota_str, contagem in distribuicao.items():
        if nota_str == 'total':
            continue
        try:
            nota = float(nota_str)
            lista.extend([nota] * int(contagem))
        except ValueError:
            continue
    return lista


def gerar_candidato(all_desenho: List[float], all_gda: List[float], all_hca: List[float], media_interna_base, info_exames: Dict[str, Tuple[float, float]]) -> float:
    indice_desenho = random.randrange(len(all_desenho))
    nota_exame_desenho = all_desenho.pop(indice_desenho)

    indice_gda = random.randrange(len(all_gda))
    indice_hca = random.randrange(len(all_hca))

    x = random.random()
    nota_exame_gda = None
    nota_exame_hca = None
    if x < PARAMS['both_probability']:
        tmp_gda = all_gda.pop(indice_gda)
        tmp_hca = all_hca.pop(indice_hca)
        if tmp_gda > tmp_hca: nota_exame_gda = tmp_gda
        else: nota_exame_hca = tmp_hca
    elif x < PARAMS['both_probability'] + PARAMS['gda_probability']:
        nota_exame_gda = all_gda.pop(indice_gda)
    else:
        nota_exame_hca = all_hca.pop(indice_hca)

    if nota_exame_gda is not None:
        nota_exame_hca_ou_gda = nota_exame_gda
        media_medias_exames = (info_exames['desenho'][0] + info_exames['gda'][0]) / 2
        media_desvios_exames = (info_exames['desenho'][1] + info_exames['gda'][1]) / 2
    elif nota_exame_hca is not None:
        nota_exame_hca_ou_gda = nota_exame_hca
        media_medias_exames = (info_exames['desenho'][0] + info_exames['hca'][0]) / 2
        media_desvios_exames = (info_exames['desenho'][1] + info_exames['hca'][1]) / 2

    media_notas_exames = (nota_exame_desenho + nota_exame_hca_ou_gda) / 2 

    exame_norm = (media_notas_exames - media_medias_exames) / media_desvios_exames
    correlacao = PARAMS['correlacao']
    erro = random.gauss(0, 1)
    interna_norm = correlacao * exame_norm + (1 - correlacao**2)**0.5 * erro

    media_interna = media_interna_base + interna_norm * PARAMS['desvio_interna']
    media_interna = min(max(media_interna, 10), 20)
    media_exames = nota_exame_desenho * 0.3 + nota_exame_hca_ou_gda * 0.2
    media_fbaup = media_interna * 0.5 + nota_exame_desenho * 0.3 + nota_exame_hca_ou_gda * 0.2

    return media_fbaup, media_interna, media_exames * 2
    

def analisar_resultados(resultados: List[Tuple[float, float, float, float]]) -> Dict[str, Dict[str, Union[float, Tuple[float, float]]]]:
    if not resultados:
        return {
            'media_fbaup': {'mean': 0, 'std': 0, 'ic95': (0,0), 'P10': 0, 'P50': 0, 'P90': 0},
            'media_interna': {'mean': 0, 'std': 0, 'ic95': (0,0), 'P10': 0, 'P50': 0, 'P90': 0},
            'nota_exame': {'mean': 0, 'std': 0, 'ic95': (0,0), 'P10': 0, 'P50': 0, 'P90': 0},
        }

    medias_fbaup = [r[0] for r in resultados]
    medias_interna = [r[1] for r in resultados]
    notas_exame = [r[2] for r in resultados]

    def calc_estatisticas(dados: List[float]) -> Dict[str, Union[float, Tuple[float, float]]]:
        mean = statistics.mean(dados)
        std = statistics.stdev(dados) if len(dados) > 1 else 0
        n = len(dados)
        ic95 = (mean - 1.96 * std / n**0.5, mean + 1.96 * std / n**0.5) if n > 1 else (mean, mean)
        sorted_dados = sorted(dados)
        p10 = sorted_dados[int(0.1 * n)]
        p50 = statistics.median(dados)
        p90 = sorted_dados[int(0.9 * n)]
        return {'mean': mean, 'std': std, 'ic95': ic95, 'P10': p10, 'P50': p50, 'P90': p90}

    return {
        'media_fbaup': calc_estatisticas(medias_fbaup),
        'media_interna': calc_estatisticas(medias_interna),
        'nota_exame': calc_estatisticas(notas_exame),
    }


def gerar_qnt_candidatos(media: int, desvio: int, minimo: int, maximo: int) -> int:
    while True:
        valor = round(random.gauss(media, desvio))
        if minimo <= valor <= maximo:
            return valor


def main():
    media_interna_base = PARAMS['media_interna_base'] + PARAMS['especulacao_variacao_media_interna']
    lista_desenho = amostrar_lista(PARAMS['exame_desenho_1f_2025'])
    lista_gda = amostrar_lista(PARAMS['exame_gda_1f_2024'])
    lista_hca = amostrar_lista(PARAMS['exame_hca_1f_2025'])

    info_exames = {
        'desenho': (statistics.mean(lista_desenho), statistics.stdev(lista_desenho)),
        'gda': (statistics.mean(lista_gda), statistics.stdev(lista_gda)),
        'hca': (statistics.mean(lista_hca), statistics.stdev(lista_hca))
    }

    ultimos_colocados = []
    lista_media_medias_internas_colocados = []
    lista_media_medias_exames_colocados = []
    lista_num_candidatos_simulacao = []
    for _ in range(PARAMS['simulacoes']):
        candidatos = []
        lista_desenho_copy = lista_desenho.copy()
        lista_gda_copy = lista_gda.copy()
        lista_hca_copy = lista_hca.copy()        

        qnt_candidatos_simulacao = gerar_qnt_candidatos(PARAMS['candidatos'], 10, PARAMS['min_candidatos'], PARAMS['max_candidatos'])
        lista_num_candidatos_simulacao.append(qnt_candidatos_simulacao)
        for _ in range(qnt_candidatos_simulacao):
            cand = gerar_candidato(lista_desenho_copy, lista_gda_copy, lista_hca_copy, media_interna_base, info_exames)
            candidatos.append(cand)

        colocados = heapq.nlargest(PARAMS['vagas'], candidatos, key=lambda x: x[0])
        lista_media_medias_internas_colocados.append(sum(c[1] for c in colocados) / len(colocados))
        lista_media_medias_exames_colocados.append(sum(c[2] for c in colocados) / len(colocados))
        ultimo_colocado = colocados[-1]
        ultimos_colocados.append(ultimo_colocado)

    estatisticas = analisar_resultados(ultimos_colocados)
    media_lista_media_medias_internas_colocados = sum(lista_media_medias_internas_colocados) / len(lista_media_medias_internas_colocados)
    media_lista_media_medias_exames_colocados = sum(lista_media_medias_exames_colocados) / len(lista_media_medias_exames_colocados)
    media_num_candidatos = sum(lista_num_candidatos_simulacao) / len(lista_num_candidatos_simulacao)

    print(f"- Previsão da média do último colocado em Desenho (FBAUP 2025): {estatisticas['media_fbaup']['mean']:.2f}")
    print(f"- Desvio-padrão: {estatisticas['media_fbaup']['std']:.2f}")
    print(f"- IC 95%: [{estatisticas['media_fbaup']['ic95'][0]:.2f}, {estatisticas['media_fbaup']['ic95'][1]:.2f}]")
    print(f"- Percentis: P10={estatisticas['media_fbaup']['P10']:.2f} | P50={estatisticas['media_fbaup']['P50']:.2f} | P90={estatisticas['media_fbaup']['P90']:.2f}")
    print(f"- Faixa provável: {estatisticas['media_fbaup']['P10']:.2f} -- {estatisticas['media_fbaup']['P90']:.2f}")

    print(f"\n- Média das médias internas últimos dos colocados: {estatisticas['media_interna']['mean']:.2f}")
    print(f"- Média das médias dos exames dos últimos colocados: {estatisticas['nota_exame']['mean']:.2f}")

    print(f"\n- Média das médias internas dos colocados: {media_lista_media_medias_internas_colocados:.2f}")
    print(f"- Média das médias dos exames dos colocados: {media_lista_media_medias_exames_colocados:.2f}")
    print(f"- Média do número de candidatos utilizado nas simulações: {media_num_candidatos:.2f}")

if __name__ == '__main__':
    main()
