"""Backend do MVP "Voz do Prato": dados, regras de negócio e KPIs (sem interface).

Regras principais
-----------------
Estrelas Michelin  : inteiros 0, 1, 2 ou 3 (escala discreta, simulada neste protótipo).
Nota do Público    : média das notas (0,5 a 5,0) suavizada com 3 notas "fantasma" de valor 3,5,
                     para que poucos votos não distorçam o ranking.
Índice Voz do Prato: Nota do Público + bônus Michelin (0,20 por estrela, máx. +0,60), limitado a 5,0.
                     Sem estrela = sem bônus (não penaliza botecos e casas fora do Guia).
"""
import datetime as dt

import pandas as pd

import gerar_dados as gd

HOJE = dt.date.today()

BONUS_POR_ESTRELA = 0.20     # peso de cada estrela Michelin no índice
PRIOR_NOTA, PRIOR_PESO = 3.5, 3
META_SELOS = 3               # selos distintos para liberar 1 sobremesa
NOTAS_VALIDAS = [k * 0.5 for k in range(1, 11)]   # 0,5 a 5,0


# ------------------------------------------------------------------ acesso a dados
def ler(arq):
    """Lê um CSV sem converter textos vazios em NaN."""
    return pd.read_csv(arq, keep_default_na=False)


def cfg():
    """Configuração da campanha: impressoes (alcance simulado) e fase."""
    return ler("kpi_base.csv").iloc[0]


def evento(tipo, u=None):
    """Registra evento de funil: acesso, cadastro, consumo, avaliacao, compartilhamento."""
    gd.adicionar("eventos.csv", {"data": str(HOJE), "usuario": u or "anon", "tipo": tipo})


def horario():
    """(aberto_agora, hora_de_fechamento). Taste: dom-qui 11h-23h; sex e sáb 11h-00h."""
    a = dt.datetime.now()
    h = a.hour + a.minute / 60
    fecha = 24 if a.weekday() in (4, 5) else 23
    return 11 <= h < fecha, ("00h" if fecha == 24 else "23h")


# ------------------------------------------------------------------ notas e ranking
def michelin_txt(n):
    """Texto das estrelas Michelin: '⭐⭐' ou 'Sem estrela'."""
    n = gd.quantizar_estrelas(n)
    return "⭐" * n if n else "Sem estrela"


def stats(av=None):
    """Tabela de restaurantes com estrelas, Nota do Público e Índice Voz do Prato.

    `av` permite calcular sobre um recorte das avaliações (ex.: últimos 7 dias).
    """
    R = ler("restaurantes.csv")
    av = ler("avaliacoes.csv") if av is None else av
    g = av.groupby("restaurante_id")["nota"].agg(["sum", "count"])
    df = R.merge(g, left_on="id", right_index=True, how="left")
    df[["sum", "count"]] = df[["sum", "count"]].fillna(0)
    df["estrelas_michelin"] = df["estrelas_michelin"].astype(int)
    df["nota_michelin"] = df["estrelas_michelin"]            # alias p/ compatibilidade com a interface
    df["michelin_txt"] = df["estrelas_michelin"].map(michelin_txt)
    df["publico"] = ((df["sum"] + PRIOR_PESO * PRIOR_NOTA) / (df["count"] + PRIOR_PESO)).round(2)
    df["indice"] = (df["publico"] + BONUS_POR_ESTRELA * df["estrelas_michelin"]).clip(upper=5).round(2)
    return df


def selos_de(u):
    """IDs dos restaurantes que o usuário já avaliou (1 selo por restaurante)."""
    av = ler("avaliacoes.csv")
    return list(av.loc[av["usuario"] == u, "restaurante_id"].unique())


def ranking_criticos():
    """Críticos da Zona Norte: 10 pontos por restaurante distinto + 1 por avaliação."""
    av, us = ler("avaliacoes.csv"), ler("usuarios.csv")
    g = av.groupby("usuario").agg(rest=("restaurante_id", "nunique"), aval=("id", "count")).reset_index()
    g["pontos"] = g["rest"] * 10 + g["aval"]
    return g.merge(us, on="usuario", how="left").sort_values("pontos", ascending=False)


# ------------------------------------------------------------------ régua de comunicação (in-app)
def notificacoes(u):
    """Lista de (ícone, título, texto) conforme a fase da campanha e o comportamento do usuário."""
    av, R = ler("avaliacoes.csv"), ler("restaurantes.csv")
    meu = av[av["usuario"] == u].sort_values(["data", "id"])
    n = meu["restaurante_id"].nunique()
    liberadas = n // META_SELOS
    resgatadas = (ler("resgates.csv")["usuario"] == u).sum()
    fase = cfg()["fase"]
    out = []
    if fase == "Pré-lançamento":
        out.append(("⏳", "Você está na lista de espera", "Avisamos no dia 1 do circuito. Prepare o paladar."))
    if fase == "Pós-circuito":
        out.append(("🗺️", "Seu mapa de selos chegou",
                    f"Você visitou {n} restaurantes e fez {len(meu)} avaliações. "
                    "Veja se entrou no top 10 dos Críticos da Zona Norte."))
    if liberadas > resgatadas:
        out.append(("🍰", "Recompensa liberada!", "Sua sobremesa por nossa conta espera na aba Selos."))
    if n == 0:
        out.append(("📲", "Sente, escaneie e opine", "Escaneie o QR da mesa e ganhe seu primeiro selo."))
    else:
        ult = R.loc[R["id"] == meu.iloc[-1]["restaurante_id"], "nome"].iloc[0]
        out.append(("🏅", f"Você ganhou o selo de {ult}",
                    f"Faltam {META_SELOS - n % META_SELOS} para sua sobremesa."))
        dias = (HOJE - pd.to_datetime(meu["data"]).max().date()).days
        if dias >= 3:
            out.append(("👋", "Ainda tem restaurante te esperando", f"Faz {dias} dias que você não avalia."))
    sem = av[pd.to_datetime(av["data"]).dt.date >= HOJE - dt.timedelta(days=7)]
    lider = stats(sem).sort_values("indice", ascending=False).iloc[0]["nome"]
    out.append(("📊", "Ranking parcial da semana", f"{lider} lidera o Índice Voz do Prato."))
    return out


# ------------------------------------------------------------------ KPIs do PDF
def kpis():
    """Indicadores de sucesso da campanha (dict). KPI principal: taxa_avaliacao."""
    ev, av = ler("eventos.csv"), ler("avaliacoes.csv")
    c = cfg()
    acessos, cadastros = (ev["tipo"] == "acesso").sum(), (ev["tipo"] == "cadastro").sum()
    consumos, shares = (ev["tipo"] == "consumo").sum(), (ev["tipo"] == "compartilhamento").sum()
    dias = av.groupby("usuario")["data"].nunique()
    liberadas = (av.groupby("usuario")["restaurante_id"].nunique() // META_SELOS).sum()
    resgatadas = len(ler("resgates.csv"))
    nps = ler("nps.csv")["nota"].astype(float)
    return {
        "alcance": int(c["impressoes"]), "acessos": int(acessos), "cadastros": int(cadastros),
        "consumos": int(consumos), "avaliacoes": len(av),
        "taxa_cadastro": cadastros / max(acessos, 1),
        "taxa_avaliacao": len(av) / max(consumos, 1),                 # KPI principal
        "aval_por_usuario": len(av) / max(av["usuario"].nunique(), 1),
        "taxa_retorno": (dias >= 2).sum() / max(len(dias), 1),
        "voltaram": int((dias >= 2).sum()), "avaliadores": len(dias),
        "liberadas": int(liberadas), "resgatadas": int(resgatadas),
        "taxa_resgate": resgatadas / max(liberadas, 1),
        "shares": int(shares), "ugc": int((av["comentario"] != "").sum()),
        "nps": ((nps >= 9).mean() - (nps <= 6).mean()) * 100 if len(nps) else 0,
    }
