"""Voz do Prato · Taste, Norte Shopping  (MVP mobile-first em Streamlit)
Rodar:  streamlit run app.py --server.address 0.0.0.0
Painel da campanha (oculto): abra o app com  ?painel=CHAVE  (ver chave_painel()).
"""
import base64
import datetime as dt
import hashlib
import html
import os
import re
import urllib.parse

import pandas as pd
import streamlit as st

import gerar_dados as gd
from backend import (HOJE, cfg, evento, horario, kpis, ler, notificacoes, ranking_criticos,
                     selos_de, stats)

st.set_page_config(page_title="Voz do Prato", page_icon="🍽️", layout="centered",
                   initial_sidebar_state="collapsed")

if not (os.path.exists("pratos.csv") and os.path.exists("eventos.csv")):
    gd.main()

esc = html.escape
ss = st.session_state
PASTA = os.path.dirname(os.path.abspath(__file__))

# ------------------------------------------------------------------ estilo
st.markdown("""<style>
/* some com barra superior, menu lateral e atalhos do Streamlit (quando o host permitir) */
header[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stSidebar"],
[data-testid="stSidebarCollapsedControl"], [data-testid="stExpandSidebarButton"],
#MainMenu, footer {display:none !important}
.block-container{max-width:480px;padding:calc(3.8rem + env(safe-area-inset-top)) 1rem 6rem 1rem}
.card{background:#1e232a;border:1px solid #2e353f;border-radius:12px;padding:12px 14px;margin:0 0 10px 0;
      line-height:1.4}
.hero{border-radius:14px;padding:20px 14px;text-align:center;margin-bottom:12px;color:#fff}
.hero .e{font-size:56px;line-height:1.1}.hero b{display:block;font-size:21px}
.hero .logo{margin:0 auto 8px auto}
.star{color:#ffb400;letter-spacing:1px}
.muted{color:#98a2b3;font-size:13px}
.pill{display:inline-block;background:#2e353f;border-radius:20px;padding:2px 10px;margin:3px 4px 0 0;font-size:12px}
.row{display:flex;gap:12px;align-items:center}
.tile{border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:30px;flex:none}
.logo{flex:none;display:block;border:1px solid #2e353f}
.trio{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:10px}
.trio div{background:#1e232a;border:1px solid #2e353f;border-radius:12px;padding:10px 4px;text-align:center}
.trio b{display:block;font-size:22px;color:#ffb400}.trio span{font-size:11px;color:#98a2b3}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px}
.stamp{border-radius:14px;padding:16px 6px;text-align:center;color:#fff;border:1px solid #2e353f}
.stamp .logo{margin:0 auto 8px auto}
.stamp.off{filter:grayscale(1);opacity:.35}
.st-key-barra{position:fixed;bottom:0;left:0;right:0;z-index:999;background:#15181d;
              border-top:1px solid #2e353f;padding:4px 8px calc(4px + env(safe-area-inset-bottom))}
.st-key-barra [role=radiogroup]{display:flex;justify-content:space-around;width:100%;max-width:480px;margin:0 auto}
.st-key-barra label{padding:6px 14px;border-radius:12px;cursor:pointer;font-size:24px;margin:0}
.st-key-barra label>div:first-child{display:none}
.st-key-barra label:has(input:checked){background:#d6203a}
</style>""", unsafe_allow_html=True)


# ------------------------------------------------------------------ helpers de interface
def estrelas(n):
    n = float(n)
    return "★" * int(n) + ("½" if n - int(n) >= 0.5 else "")


def card(conteudo):
    return f"<div class='card'>{conteudo}</div>"


@st.cache_data(show_spinner=False)
def logo_uri(rid):
    """Foto de perfil do restaurante (assets/logos/<id>.jpg) como data URI."""
    p = os.path.join(PASTA, "assets", "logos", f"{rid}.jpg")
    if not os.path.exists(p):
        return ""
    with open(p, "rb") as f:
        return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()


def css_logos():
    """Uma regra CSS por logo. Vai no CSS global, enviado uma vez por sessão (não a cada tela)."""
    ids = ler("restaurantes.csv")["id"]
    return "".join(f".lg{i}{{background:url({logo_uri(int(i))}) center/cover no-repeat #fff}}"
                   for i in ids if logo_uri(int(i)))


def logo(r, px=56, raio=12):
    if not logo_uri(int(r["id"])):     # sem imagem: usa o emoji provisório
        return f"<div class='tile' style='background:{r['cor']};width:{px}px;height:{px}px'>{r['selo']}</div>"
    return f"<div class='logo lg{int(r['id'])}' style='width:{px}px;height:{px}px;border-radius:{raio}px'></div>"


def review_html(a, nome=None):
    tags = "".join(f"<span class='pill'>{esc(t)}</span>" for t in str(a["tags"]).split("|") if t)
    cab = f"<b>{esc(a['usuario'])}</b>" + (f" em <b>{esc(nome)}</b>" if nome else "")
    com = f"<br>{esc(a['comentario'])}" if a["comentario"] else ""
    return card(f"{cab} <span class='star'>{estrelas(a['nota'])}</span><br>"
                f"<span class='muted'>{esc(a['prato'])} · {a['data']}</span>{com}<br>{tags}")


def notif_html(ns):
    return "".join(card(f"{ic} <b>{esc(tit)}</b><br><span class='muted'>{esc(tx)}</span>") for ic, tit, tx in ns)


# ------------------------------------------------------------------ callbacks
def ir(pagina, rid=None):
    ss.pagina = pagina
    if rid is not None:
        ss.sel = rid


def voltar_lista():
    ss.sel = None


def curtir(aid):
    if aid in ss.liked:
        return
    df = ler("avaliacoes.csv")
    df.loc[df["id"] == aid, "curtidas"] += 1
    df.to_csv("avaliacoes.csv", index=False, encoding="utf-8")
    ss.liked.add(aid)


def alternar_lista(u, rid):
    q = ler("querer_ir.csv")
    tem = (q["usuario"] == u) & (q["restaurante_id"] == rid)
    if tem.any():
        q[~tem].to_csv("querer_ir.csv", index=False, encoding="utf-8")
    else:
        gd.adicionar("querer_ir.csv", {"usuario": u, "restaurante_id": rid})


# ------------------------------------------------------------------ telas
def tela_cadastro():
    st.markdown("<div class='hero' style='background:linear-gradient(160deg,#d6203a,#5c0b19)'>"
                "<div class='e'>🍽️</div><b>Voz do Prato</b>Michelin dando voz ao seu paladar</div>",
                unsafe_allow_html=True)
    st.markdown("**Quem prova, dá a nota.** Você não precisa ser especialista para ter uma opinião que importa.")
    with st.form("cad"):
        ap = st.text_input("Seu apelido", max_chars=20, placeholder="ex.: ana.meier")
        bairro = st.selectbox("Seu bairro", gd.BAIRROS)
        ok = st.form_submit_button("Entrar", type="primary", width="stretch")
    if ok:
        ap = ap.strip().lower()
        if not re.fullmatch(r"[a-z0-9_.]{3,20}", ap):
            st.error("Use de 3 a 20 caracteres: letras minúsculas, números, ponto ou _ (sem espaços).")
            return
        if ap not in set(ler("usuarios.csv")["usuario"]):
            gd.adicionar("usuarios.csv", {"usuario": ap, "bairro": bairro, "criado_em": str(HOJE)})
            evento("cadastro", ap)
        ss.user = ap
        st.query_params["u"] = ap
        st.rerun()
    st.caption("Protótipo acadêmico: avaliações, estrelas Michelin e preços são simulados.")


def pg_home(u):
    fase = cfg()["fase"]
    ns = notificacoes(u)
    aberto, fecha = horario()
    st.markdown(f"#### Olá, {esc(u)} 👋")
    st.caption(("🟢 Taste aberto agora, até " + fecha) if aberto else "🔴 Taste fechado agora, abre às 11h")
    if fase == "Pré-lançamento":
        st.info("A campanha ainda não começou. Você está na lista de espera.")
    st.markdown(notif_html(ns[:1]), unsafe_allow_html=True)
    if len(ns) > 1:
        with st.expander(f"🔔 Mais {len(ns) - 1} notificações"):
            st.markdown(notif_html(ns[1:]), unsafe_allow_html=True)

    av, R = ler("avaliacoes.csv"), ler("restaurantes.csv")
    nomes = R.set_index("id")["nome"]
    av["d"] = pd.to_datetime(av["data"]).dt.date

    st.markdown("##### Em alta esta semana")
    top = stats(av[av["d"] >= HOJE - dt.timedelta(days=7)]).sort_values("indice", ascending=False).head(3)
    for i, (_, r) in enumerate(top.iterrows(), 1):
        st.markdown(card(f"<div class='row'>{logo(r)}"
                         f"<div><b>{i}. {esc(r['nome'])}</b><br><span class='star'>{estrelas(round(r['publico'] * 2) / 2)}</span> "
                         f"<span class='muted'>Índice {r['indice']}</span></div></div>"), unsafe_allow_html=True)
        st.button("Ver restaurante", key=f"alta{r['id']}", on_click=ir, args=("explorar", int(r["id"])),
                  width="stretch")

    st.markdown("##### Destaques")
    blocos = []
    dmax = av["d"].max()
    dia = av[av["d"] == dmax]
    if len(dia):
        crit = dia.groupby("usuario")["curtidas"].sum().idxmax()
        blocos.append(card(f"🎙️ <b>Crítico do dia</b><br>{esc(crit)} <span class='muted'>({dmax})</span>"))
    pr = av[av["prato"] != ""].groupby(["restaurante_id", "prato"])["nota"].agg(["mean", "count"]).reset_index()
    pr = pr[pr["count"] >= 3].sort_values(["mean", "count"], ascending=False)
    if len(pr):
        p = pr.iloc[0]
        blocos.append(card(f"🥇 <b>Prato mais bem votado</b><br>{esc(p['prato'])} · {esc(nomes[p['restaurante_id']])}<br>"
                           f"<span class='star'>{estrelas(round(p['mean'] * 2) / 2)}</span> "
                           f"<span class='muted'>{p['mean']:.1f} · {int(p['count'])} votos</span>"))
    st.markdown("".join(blocos), unsafe_allow_html=True)

    st.markdown("##### Críticos da Zona Norte")
    st.markdown("".join(
        card(f"<b>{i}. {esc(c['usuario'])}</b> <span class='muted'>{esc(str(c['bairro']))} · "
             f"{int(c['rest'])} selos · {int(c['aval'])} avaliações</span>")
        for i, (_, c) in enumerate(ranking_criticos().head(5).iterrows(), 1)), unsafe_allow_html=True)

    st.markdown("##### Atividade recente")
    st.markdown("".join(review_html(a, nomes[a["restaurante_id"]])
                        for _, a in av.sort_values("id", ascending=False).head(5).iterrows()),
                unsafe_allow_html=True)


def detalhe(u, rid):
    S = stats()
    r = S[S["id"] == rid].iloc[0]
    st.button("← Voltar", on_click=voltar_lista)
    st.markdown(f"<div class='hero' style='background:{r['cor']}'>{logo(r, 96, 48)}"
                f"<b>{esc(r['nome'])}</b>{esc(r['categoria'])} · {r['preco']}</div>", unsafe_allow_html=True)
    st.write(r["descricao"])
    st.markdown(f"<div class='trio'><div><b>{r['michelin_txt']}</b><span>Estrelas Michelin<br>(simuladas)</span></div>"
                f"<div><b>{r['publico']}</b><span>Nota do Público<br>{int(r['count'])} avaliações</span></div>"
                f"<div><b>{r['indice']}</b><span>Índice<br>Voz do Prato</span></div></div>", unsafe_allow_html=True)

    q = ler("querer_ir.csv")
    na_lista = ((q["usuario"] == u) & (q["restaurante_id"] == rid)).any()
    st.button("✓ Na sua lista" if na_lista else "➕ Quero provar", key="qp", on_click=alternar_lista,
              args=(u, rid), width="stretch")
    st.button("📲 Avaliar (tenho um código de mesa)", key="av_ir", on_click=ir, args=("avaliar",),
              width="stretch", type="primary")

    av = ler("avaliacoes.csv")
    av = av[av["restaurante_id"] == rid]
    if len(av):
        st.markdown("##### Distribuição das notas")
        st.bar_chart(av["nota"].astype(float).value_counts()
                     .reindex([k * 0.5 for k in range(1, 11)], fill_value=0))
        pr = av.groupby("prato")["nota"].agg(["mean", "count"]).sort_values("mean", ascending=False)
        st.markdown("##### Pratos")
        st.markdown("".join(
            card(f"<b>{esc(prato)}</b> <span class='star'>{estrelas(round(p['mean'] * 2) / 2)}</span> "
                 f"<span class='muted'>{p['mean']:.1f} · {int(p['count'])} votos</span>")
            for prato, p in pr.iterrows()), unsafe_allow_html=True)
        tg = av["tags"].str.split("|").explode()
        tg = tg[tg != ""].value_counts().head(5)
        st.markdown("".join(f"<span class='pill'>{esc(t)} · {n}</span>" for t, n in tg.items()),
                    unsafe_allow_html=True)
        st.markdown("##### Avaliações populares")
        for _, a in av.sort_values(["curtidas", "id"], ascending=False).head(5).iterrows():
            st.markdown(review_html(a), unsafe_allow_html=True)
            st.button(f"❤ {int(a['curtidas'])}", key=f"like{a['id']}", on_click=curtir, args=(int(a["id"]),))
    else:
        st.info("Ainda sem avaliações. Seja o primeiro a dar a nota.")


def pg_explorar(u):
    if ss.sel:
        return detalhe(u, ss.sel)
    st.markdown("#### Restaurantes do Taste")
    aberto, fecha = horario()
    st.caption(f"2º piso do pátio · Norte Shopping · {'🟢 aberto agora' if aberto else '🔴 fechado agora'}")
    S = stats()
    tipo = st.pills("Tipo de comida", sorted(S["categoria"].unique()), selection_mode="multi")
    preco = st.pills("Faixa de preço (estimada)", ["$", "$$", "$$$"], selection_mode="multi")
    ordem = st.selectbox("Ordenar por", ["Índice Voz do Prato", "Nota do Público", "Mais avaliados", "Nome"])
    if tipo:
        S = S[S["categoria"].isin(tipo)]
    if preco:
        S = S[S["preco"].isin(preco)]
    chave, asc = {"Índice Voz do Prato": ("indice", False), "Nota do Público": ("publico", False),
                  "Mais avaliados": ("count", False), "Nome": ("nome", True)}[ordem]
    S = S.sort_values(chave, ascending=asc)
    if S.empty:
        st.info("Nenhum restaurante com esses filtros.")
    for _, r in S.iterrows():
        st.markdown(card(f"<div class='row'>{logo(r)}<div>"
                         f"<b>{esc(r['nome'])}</b><br><span class='muted'>{esc(r['categoria'])} · {r['preco']}</span><br>"
                         f"<span class='star'>{estrelas(round(r['publico'] * 2) / 2)}</span> "
                         f"<span class='muted'>{r['publico']:.1f} · {int(r['count'])} avaliações</span></div></div>"),
                    unsafe_allow_html=True)
        st.button("Ver restaurante", key=f"ver{r['id']}", on_click=ir, args=("explorar", int(r["id"])),
                  width="stretch")


def pg_avaliar(u):
    fase = cfg()["fase"]
    st.markdown("#### 📲 Avaliar")
    if fase != "Circuito":
        st.warning("A avaliação só abre durante o circuito." if fase == "Pré-lançamento"
                   else "O circuito terminou. Veja seu mapa de selos no perfil.")
        return
    st.caption("Sente, consuma e escaneie o QR da mesa. Só avalia quem esteve lá.")
    cod = st.text_input("Código da mesa", value=ss.get("mesa", ""), placeholder="ex.: 3-M2").strip().upper()
    if cod:
        try:
            a, b = cod.split("-M")
            rid, mesa = int(a), int(b)
            R = ler("restaurantes.csv")
            r = R[R["id"] == rid].iloc[0]
        except (ValueError, IndexError):
            st.error("Código inválido. Escaneie o QR da mesa novamente.")
            return
        if (cod, str(HOJE)) not in ss.consumos:
            ss.consumos.add((cod, str(HOJE)))
            evento("consumo", u)
        st.markdown(card(f"<div class='row'>{logo(r, 48, 10)}<div><b>{esc(r['nome'])}</b><br>"
                         f"<span class='muted'>Mesa {mesa} confirmada ✓</span></div></div>"), unsafe_allow_html=True)
        pratos = list(ler("pratos.csv").query("restaurante_id == @rid")["prato"]) + ["Outro prato"]
        prato = st.selectbox("Qual prato você avalia?", pratos)
        nota = st.select_slider("Sua nota", options=[k * 0.5 for k in range(1, 11)], value=4.0)
        st.markdown(f"<span class='star' style='font-size:28px'>{estrelas(nota)}</span>", unsafe_allow_html=True)
        tags = st.pills("O que marcou?", gd.TAGS_POS + gd.TAGS_NEG, selection_mode="multi")
        com = st.text_area("Seu veredito (opcional)", max_chars=140)
        if st.button("Publicar avaliação", type="primary", width="stretch"):
            av = ler("avaliacoes.csv")
            if ((av["usuario"] == u) & (av["restaurante_id"] == rid) & (av["data"] == str(HOJE))).any():
                st.warning("Você já avaliou este restaurante hoje.")
            else:
                antes = set(selos_de(u))
                gd.adicionar("avaliacoes.csv", {"id": int(av["id"].max()) + 1, "usuario": u, "restaurante_id": rid,
                                                "prato": prato, "nota": nota, "tags": "|".join(tags or []),
                                                "comentario": com.strip(), "data": str(HOJE), "curtidas": 0})
                evento("avaliacao", u)
                ss.ultima = {"rid": rid, "nome": r["nome"], "nota": nota, "novo": rid not in antes,
                             "n": len(set(selos_de(u))), "share": False}
                st.balloons()

    ult = ss.get("ultima")
    if ult:
        R = ler("restaurantes.csv")
        rr = R[R["id"] == ult["rid"]].iloc[0]
        titulo = "Selo conquistado: " if ult["novo"] else "Avaliação publicada: "
        if ult["n"] >= 3:
            progresso = "Sobremesa liberada na aba Selos!"
        else:
            progresso = "Faltam " + str(3 - ult["n"]) + " para a sobremesa."
        st.markdown(card(f"<div style='text-align:center'><div style='display:flex;justify-content:center'>{logo(rr, 72, 36)}</div>"
                         f"<br><b>{titulo}{esc(ult['nome'])}</b><br>"
                         f"<span class='muted'>Você tem {ult['n']} selo(s). {progresso}</span></div>"),
                    unsafe_allow_html=True)
        if st.button("📤 Compartilhar", width="stretch"):
            evento("compartilhamento", u)
            ss.ultima["share"] = True
        if ult["share"]:
            txt = (f"Avaliei {ult['nome']} no Voz do Prato (Taste · Norte Shopping): {estrelas(ult['nota'])}! "
                   "Quem prova, dá a nota. #VozDoPrato")
            st.link_button("Abrir no WhatsApp", "https://wa.me/?text=" + urllib.parse.quote(txt),
                           width="stretch")


def pg_selos(u):
    R = ler("restaurantes.csv")
    meus = set(selos_de(u))
    n = len(meus)
    st.markdown("#### 🏅 Meus selos")
    st.caption("Colecione os 8 selos do Taste.")
    cel = "".join(
        f"<div class='stamp{'' if r['id'] in meus else ' off'}' style='background:{r['cor']}'>"
        f"{logo(r, 72, 36)}<b>{esc(r['nome'])}{'' if r['id'] in meus else ' 🔒'}</b></div>"
        for _, r in R.iterrows())
    st.markdown(f"<div class='grid'>{cel}</div>", unsafe_allow_html=True)
    st.progress(min((n % 3) / 3 if n < 8 else 1.0, 1.0), text=f"{n} de 8 selos")

    res = ler("resgates.csv")
    meus_res = res[res["usuario"] == u]
    pend = n // 3 - len(meus_res)
    if pend > 0:
        st.success(f"🍰 {pend} sobremesa(s) grátis liberada(s)!")
        if st.button("Resgatar sobremesa", type="primary", width="stretch"):
            cod = "VP-" + hashlib.md5(f"{u}{len(meus_res)}".encode()).hexdigest()[:6].upper()
            gd.adicionar("resgates.csv", {"usuario": u, "codigo": cod, "data": str(HOJE)})
            st.rerun()
    else:
        st.info(f"Faltam {3 - n % 3} selo(s) para a próxima sobremesa grátis.")
    if len(meus_res):
        st.markdown("".join(
            card(f"🎟️ <b>{esc(v['codigo'])}</b><br><span class='muted'>Mostre ao atendente · {v['data']}</span>")
            for _, v in meus_res.iterrows()), unsafe_allow_html=True)
    if n == 8:
        st.markdown(card("🏆 <b>Crítico completo do Taste</b><br><span class='muted'>Você coletou todos os selos.</span>"),
                    unsafe_allow_html=True)


def pg_perfil(u):
    us, av, R = ler("usuarios.csv"), ler("avaliacoes.csv"), ler("restaurantes.csv")
    nomes = R.set_index("id")["nome"]
    bairro = us.loc[us["usuario"] == u, "bairro"].iloc[0] if (us["usuario"] == u).any() else "-"
    meu = av[av["usuario"] == u].sort_values("id", ascending=False)
    n = len(set(meu["restaurante_id"]))
    nivel = "Provador" if n < 3 else ("Crítico" if n < 6 else "Crítico da Zona Norte")
    avatar = ["🧑‍🍳", "😋", "🍴", "🥘", "🍻"][int(hashlib.md5(u.encode()).hexdigest(), 16) % 5]
    st.markdown(card(f"<div class='row'><div class='tile' style='background:#2e353f;width:56px;height:56px'>{avatar}</div><div>"
                     f"<b>{esc(u)}</b><br><span class='muted'>{esc(str(bairro))} · {nivel}</span></div></div>"),
                unsafe_allow_html=True)
    media = f"{meu['nota'].astype(float).mean():.1f}" if len(meu) else "-"
    st.markdown(f"<div class='trio'><div><b>{len(meu)}</b><span>Avaliações</span></div>"
                f"<div><b>{n}</b><span>Selos</span></div><div><b>{media}</b><span>Nota média</span></div></div>",
                unsafe_allow_html=True)

    st.markdown("##### Meu diário")
    if len(meu):
        st.markdown("".join(review_html(a, nomes[a["restaurante_id"]]) for _, a in meu.head(8).iterrows()),
                    unsafe_allow_html=True)
    else:
        st.info("Seu diário está vazio. Escaneie um QR de mesa para registrar a primeira.")

    q = ler("querer_ir.csv")
    q = q[q["usuario"] == u]
    st.markdown("##### Quero provar")
    st.write(", ".join(q["restaurante_id"].map(nomes)) if len(q) else "Nenhum restaurante na lista.")

    if st.button("Sair da conta", width="stretch"):
        ss.user = None
        st.query_params.pop("u", None)
        st.rerun()


# ------------------------------------------------------------------ painel da campanha (oculto)
REGUA = pd.DataFrame([
    ("Pré-lançamento", "D-21", "Teaser: “A Michelin vai ouvir você.”", "Redes", "Externo"),
    ("Pré-lançamento", "D-14", "Revelação da campanha e dos restaurantes", "Redes", "Externo"),
    ("Pré-lançamento", "D-10", "Bastidores com chefs e donos de boteco", "Redes", "Externo"),
    ("Pré-lançamento", "D-7", "Pré-cadastro e lista de espera", "App", "No app"),
    ("Pré-lançamento", "D-3", "Anúncio dos selos de cada restaurante", "App/redes", "No app"),
    ("Pré-lançamento", "D-1", "Contagem regressiva e “como funciona”", "E-mail/WhatsApp", "Externo"),
    ("Circuito", "Dia 1", "Abertura no shopping e lives", "Shopping", "Externo"),
    ("Circuito", "Diário", "Crítico do dia e prato mais votado", "App/stories", "No app"),
    ("Circuito", "Semanal", "Ranking parcial", "App", "No app"),
    ("Circuito", "Após 1º selo", "Push: faltam X para a recompensa", "App", "No app"),
    ("Circuito", "3 dias sem uso", "Push: ainda tem restaurante te esperando", "App", "No app"),
    ("Pós-circuito", "D+1", "Agradecimento e mapa de selos", "App", "No app"),
    ("Pós-circuito", "D+7", "Resultado final e Críticos da Zona Norte", "App/redes", "No app"),
    ("Pós-circuito", "D+15", "Convite para a próxima edição", "App", "Externo"),
    ("Pós-circuito", "D+30", "Pesquisa de satisfação (fora do MVP)", "E-mail", "Externo"),
], columns=["Fase", "Quando", "Ação", "Canal", "Neste MVP"])


def chave_painel():
    """Chave do painel: st.secrets['painel_key'], variável PAINEL_KEY ou padrão."""
    try:
        return str(st.secrets["painel_key"])
    except Exception:
        return os.environ.get("PAINEL_KEY", "voz2026")


def painel():
    st.button("← Voltar ao app", on_click=lambda: st.query_params.pop("painel", None))
    st.markdown("#### 📊 Painel da campanha")
    st.caption("Modo apresentação. Dados simulados e os gerados por você durante o teste.")
    k = kpis()
    t1, t2, t3, t4, t5 = st.tabs(["KPIs", "Funil", "Régua", "Copy", "Config"])
    with t1:
        st.markdown(card(f"<b>KPI principal: taxa de avaliação após consumo</b><br>"
                         f"<span class='star' style='font-size:30px'>{k['taxa_avaliacao']:.0%}</span><br>"
                         f"<span class='muted'>{k['avaliacoes']} avaliações ÷ {k['consumos']} consumos validados</span>"),
                    unsafe_allow_html=True)
        linhas = [
            ("Alcance (simulado)", f"{k['alcance']:,}".replace(",", "."), "Pessoas impactadas"),
            ("Taxa de cadastro", f"{k['taxa_cadastro']:.0%}", f"{k['cadastros']} cadastros ÷ {k['acessos']} acessos"),
            ("Avaliações por usuário", f"{k['aval_por_usuario']:.1f}", "Participação média"),
            ("Taxa de retorno", f"{k['taxa_retorno']:.0%}", f"{k['voltaram']} de {k['avaliadores']} avaliaram em 2+ dias"),
            ("Taxa de resgate", f"{k['taxa_resgate']:.0%}", f"{k['resgatadas']} de {k['liberadas']} liberadas"),
            ("Compartilhamentos / UGC", f"{k['shares']} / {k['ugc']}", "Compartilhamentos / avaliações com texto"),
        ]
        st.markdown("".join(card(f"<div style='display:flex;justify-content:space-between'><b>{nome}</b>"
                                 f"<span class='star'>{val}</span></div><span class='muted'>{desc}</span>")
                            for nome, val, desc in linhas), unsafe_allow_html=True)
    with t2:
        et = pd.Series({"1 Acessos (topo)": k["acessos"], "2 Cadastros (meio)": k["cadastros"],
                        "3 Consumos validados (fundo)": k["consumos"], "4 Avaliações": k["avaliacoes"],
                        "5 Voltaram (retenção)": k["voltaram"], "6 Resgates": k["resgatadas"]})
        st.bar_chart(et, horizontal=True)
        st.caption("Funil do PDF: topo (atração) → meio (consideração) → fundo (conversão) → pós (retenção).")
    with t3:
        st.info(f"Fase atual no app: **{cfg()['fase']}**")
        st.dataframe(REGUA, hide_index=True, width="stretch")
    with t4:
        st.markdown("**Cartão de mesa (QR)**")
        st.code("Você sentou. Você provou. Agora você opina.\nEscaneie, avalie este prato e ganhe o selo "
                "exclusivo de [Restaurante].\nMichelin dando voz ao público. #VozDoPrato", language=None)
        st.markdown("**Push de retenção**")
        st.code("🏅 Você já tem 2 selos! Falta 1 para a sobremesa por nossa conta. Qual será o próximo?",
                language=None)
        st.markdown("**E-mail pós-circuito**")
        st.code("Assunto: Seu mapa de selos chegou 🗺\nVocê visitou X restaurantes e fez Y avaliações. "
                "Cada uma ajudou a mostrar a força da gastronomia da Zona Norte.", language=None)
    with t5:
        c = cfg()
        opc = ["Pré-lançamento", "Circuito", "Pós-circuito"]
        fase = st.selectbox("Fase da campanha (simula a régua)", opc, index=opc.index(c["fase"]))
        alc = st.number_input("Alcance (simulado)", value=int(c["impressoes"]), step=1000)
        if st.button("Salvar configuração", width="stretch"):
            pd.DataFrame([(alc, fase)], columns=["impressoes", "fase"]).to_csv("kpi_base.csv", index=False)
            st.success("Salvo.")
        st.divider()
        if st.checkbox("Confirmo apagar tudo e recriar os dados de demonstração") and \
                st.button("Recriar dados", width="stretch"):
            gd.main()
            ss.user = None
            st.rerun()


# ------------------------------------------------------------------ app
PAGINAS = {"home": pg_home, "explorar": pg_explorar, "avaliar": pg_avaliar,
           "selos": pg_selos, "perfil": pg_perfil}
NAV = {"home": "🏠", "explorar": "🍽️", "avaliar": "📲", "selos": "🏅", "perfil": "👤"}


@st.fragment
def corpo():
    """Só esta parte roda de novo ao trocar de aba (o resto do script é preservado)."""
    PAGINAS[ss.pagina](ss.user)
    with st.container(key="barra"):
        st.radio("Navegação", list(NAV), format_func=NAV.get, key="pagina", horizontal=True,
                 label_visibility="collapsed")


ss.setdefault("pagina", "home")
ss.setdefault("sel", None)
ss.setdefault("user", None)
ss.setdefault("liked", set())
ss.setdefault("consumos", set())

qp = st.query_params
if ss.user is None and qp.get("u") in set(ler("usuarios.csv")["usuario"]):
    ss.user = qp["u"]
if qp.get("mesa") and not ss.get("mesa_lida"):      # QR da mesa abre direto em "Avaliar"
    ss.mesa, ss.mesa_lida, ss.pagina = qp["mesa"], True, "avaliar"
if not ss.get("acesso_ok"):
    evento("acesso", ss.user)
    ss.acesso_ok = True

st.markdown(f"<style>{css_logos()}</style>", unsafe_allow_html=True)   # logos: enviados 1x por sessão

if qp.get("painel") == chave_painel():              # painel só por link com chave
    painel()
elif ss.user is None:
    tela_cadastro()
else:
    corpo()
