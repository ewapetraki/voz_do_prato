"""Gera os CSVs do MVP "Voz do Prato".

REAIS: os 8 restaurantes do Taste (Norte Shopping) e os pratos citados na página
       https://norteshopping.com.br/taste-lab/ (consultada em 12/11/2026).
SIMULADOS: usuários, avaliações, curtidas, eventos, resgates, estrelas Michelin,
           faixa de preço e alcance. Servem só para demonstrar o conceito.

ESTRELAS MICHELIN: escala DISCRETA de 0 a 3 (inteiros), como no Guia real:
    0 = sem estrela | 1 = muito boa cozinha | 2 = excelente | 3 = excepcional
"""
import csv
import datetime as dt
import random

import pandas as pd

ESTRELAS_VALIDAS = (0, 1, 2, 3)


def quantizar_estrelas(x):
    """Converte qualquer valor numérico para a escala discreta 0-3 (arredonda e limita)."""
    return int(min(3, max(0, round(float(x)))))


BAIRROS = ["Cachambi", "Méier", "Madureira", "Tijuca", "Penha",
           "Vila Isabel", "Engenho Novo", "Ilha do Governador", "Outro"]
NOMES = ["ana", "bruno", "carla", "diego", "edu", "fabi", "gabi", "hugo", "iara", "joao",
         "kelly", "leo", "mari", "nando", "olga", "pedro", "quel", "rafa", "sara", "tiago"]

# id, nome, categoria, descrição (parafraseada do site), estrelas Michelin 0-3 (SIMULADAS),
# selo, cor, faixa de preço (ESTIMADA p/ demo)
RESTAURANTES = [
    (1, "Bobô", "Bar e hambúrguer autoral",
     "Comidas e drinks autorais, do hambúrguer de pão de alho à costelinha suína com barbecue.",
     0, "🍔", "#6b3f2a", "$$"),
    (2, "Cachambeer", "Brasileira e petiscos",
     "Casa com mais de 20 anos de história, patrimônio cultural carioca, famosa pela costela no bafo.",
     1, "🍖", "#7a2e2e", "$$"),
    (3, "Do Batista", "Brasileira",
     "Receitas que homenageiam as raízes brasileiras, como feijoada, baião de dois e picadinho, "
     "sob comando do chef João Batista.",
     3, "🫘", "#5a4520", "$$"),
    (4, "La Plancha Brasa", "Frutos do mar",
     "Cozinha focada em frutos do mar frescos, com executivos, petiscos e pratos para compartilhar.",
     1, "🦐", "#1f5568", "$$$"),
    (5, "Noi", "Cervejaria",
     "Cervejas autorais com muita personalidade, premiadas pela qualidade e variedade.",
     0, "🍺", "#6a5513", "$$"),
    (6, "Wiki Wiki", "Poke e saudável",
     "Meio havaiano, meio carioca: monte seu poke, salada, wrap ou omelete do seu jeito.",
     0, "🥗", "#1f6040", "$$"),
    (7, "Eiyo Sushi", "Japonesa",
     "Rodízio com pratos surpreendentes ou menu à la carte de culinária japonesa.",
     1, "🍣", "#53244f", "$$"),
    (8, "Blend Parrilla", "Churrasco",
     "Churrasco na lenha e na brasa ao jeito carioca, de executivo a happy hour.",
     2, "🥩", "#662f22", "$$$"),
]

# Pratos/linhas de cardápio citados nas descrições do site (não é o cardápio completo)
PRATOS = {
    1: ["Hambúrguer de pão de alho", "Costelinha suína ao barbecue", "Drinks autorais"],
    2: ["Costela no bafo", "Petiscos", "Prato executivo"],
    3: ["Feijoada", "Baião de dois", "Picadinho"],
    4: ["Frutos do mar (executivo)", "Petiscos do mar", "Prato para compartilhar"],
    5: ["Cervejas autorais"],
    6: ["Poke", "Wrap", "Omelete", "Salada"],
    7: ["Rodízio", "Menu à la carte"],
    8: ["Churrasco executivo", "Happy hour"],
}

TAGS_POS = ["Tempero de casa", "Vale o preço", "Ambiente animado", "Porção generosa",
            "Atendimento nota 10", "Voltaria"]
TAGS_NEG = ["Demorou um pouco", "Achei caro", "Esperava mais"]
COM_POS = ["Voltaria com certeza", "Ótimo custo-benefício", "Ambiente animado",
           "Porção generosa", "Gostei muito do tempero"]
COM_NEU = ["Foi ok", "Bom, mas nada demais", "Atendimento razoável"]
COM_NEG = ["Esperava mais", "Demorou um pouco", "Achei caro pelo que veio"]

MEDIA = {1: 3.9, 2: 4.2, 3: 4.4, 4: 3.8, 5: 3.6, 6: 3.5, 7: 3.9, 8: 4.1}


def _salvar(nome, linhas, colunas):
    pd.DataFrame(linhas, columns=colunas).to_csv(nome, index=False, encoding="utf-8")


def main(seed=7):
    random.seed(seed)
    hoje = dt.date.today()
    dia = lambda n: str(hoje - dt.timedelta(days=n))

    assert all(r[4] in ESTRELAS_VALIDAS for r in RESTAURANTES), "estrelas Michelin devem ser inteiros de 0 a 3"
    _salvar("restaurantes.csv", RESTAURANTES,
            ["id", "nome", "categoria", "descricao", "estrelas_michelin", "selo", "cor", "preco"])
    _salvar("pratos.csv", [(rid, p) for rid, ps in PRATOS.items() for p in ps],
            ["restaurante_id", "prato"])

    # usuários simulados
    usuarios = []
    for i in range(36):
        usuarios.append((f"{NOMES[i % 20]}_{i:02d}", random.choice(BAIRROS[:-1]), dia(random.randint(2, 14))))
    _salvar("usuarios.csv", usuarios, ["usuario", "bairro", "criado_em"])
    handles = [u[0] for u in usuarios]
    pesos = [random.choice([1, 1, 2, 4]) for _ in handles]

    # avaliações simuladas
    vistos, avals = set(), []
    pesos_dias = [3, 3, 3, 2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1]
    while len(avals) < 220:
        u = random.choices(handles, pesos)[0]
        rid = random.randint(1, 8)
        d = dia(random.choices(range(14), pesos_dias)[0])
        if (u, rid, d) in vistos:
            continue
        vistos.add((u, rid, d))
        nota = min(5, max(1, round(random.gauss(MEDIA[rid], 0.9))))   # estrelas inteiras: 1 a 5
        if nota >= 4:
            com, tags = random.choice(COM_POS), random.sample(TAGS_POS, 2)
        elif nota >= 3:
            com, tags = random.choice(COM_NEU), random.sample(TAGS_POS[:3] + TAGS_NEG, 1)
        else:
            com, tags = random.choice(COM_NEG), random.sample(TAGS_NEG, 1)
        avals.append((len(avals) + 1, u, rid, random.choice(PRATOS[rid]), nota,
                      "|".join(tags), com, d, random.randint(0, 12)))
    _salvar("avaliacoes.csv", avals,
            ["id", "usuario", "restaurante_id", "prato", "nota", "tags", "comentario", "data", "curtidas"])

    # eventos (base dos KPIs): acesso, cadastro, consumo, avaliacao, compartilhamento
    ev = []
    for u, _, criado in usuarios:
        ev.append((criado, u, "cadastro"))
        ev += [(criado, u, "acesso") for _ in range(random.randint(2, 4))]
    ev += [(dia(random.randint(0, 13)), "anon", "acesso") for _ in range(150)]
    for _, u, rid, _, _, _, _, d, _ in avals:
        ev.append((d, u, "consumo"))
        ev.append((d, u, "avaliacao"))
        if random.random() < 0.25:
            ev.append((d, u, "compartilhamento"))
    ev += [(dia(random.randint(0, 13)), random.choice(handles), "consumo") for _ in range(90)]
    _salvar("eventos.csv", ev, ["data", "usuario", "tipo"])

    # resgates simulados
    com_aval = sorted({a[1] for a in avals})
    resg = []
    for u in com_aval:
        n = len({a[2] for a in avals if a[1] == u})
        if n >= 3 and random.random() < 0.6:
            resg.append((u, f"VP-{random.randint(0, 0xFFFFFF):06X}", dia(random.randint(0, 5))))
    _salvar("resgates.csv", resg, ["usuario", "codigo", "data"])

    _salvar("querer_ir.csv", [], ["usuario", "restaurante_id"])
    _salvar("likes.csv", [], ["usuario", "avaliacao_id"])
    _salvar("kpi_base.csv", [(48200, "Circuito")], ["impressoes", "fase"])  # alcance SIMULADO
    print("Dados gerados.")


def garantir():
    """Cria arquivos opcionais que não existiam em versões antigas dos dados (sem apagar nada)."""
    import os
    if not os.path.exists("likes.csv"):
        _salvar("likes.csv", [], ["usuario", "avaliacao_id"])


def adicionar(arquivo, linha):
    """Acrescenta uma linha (dict) ao CSV, respeitando o cabeçalho."""
    cols = list(pd.read_csv(arquivo, nrows=0).columns)
    with open(arquivo, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=cols).writerow(linha)


if __name__ == "__main__":
    main()
