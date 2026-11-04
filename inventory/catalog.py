"""Catálogo comercial proposto; cobrança externa ainda desativada."""

PLANS = [
    {
        "id": "basico",
        "name": "Básico",
        "accounts": 1,
        "products": 50,
        "price_cents": 0,
        "description": "Experimente o essencial por um mês.",
        "inherits": None,
        "features": [
            {"group": "Estoque", "name": "Cadastro de itens", "available": True},
            {"group": "Estoque", "name": "Entradas e saídas", "available": True},
            {"group": "Estoque", "name": "Alertas de estoque baixo", "available": True},
            {"group": "Relatórios", "name": "Relatório básico CSV", "available": True},
            {"group": "Acesso", "name": "Acesso multidispositivo", "available": False},
            {
                "group": "Integrações",
                "name": "Backup na conta Google do usuário",
                "available": False,
            },
            {"group": "Atendimento", "name": "Suporte por e-mail", "available": False},
        ],
        "trial_months": 1,
    },
    {
        "id": "completo",
        "name": "Completo",
        "accounts": None,
        "products": None,
        "price_cents": 15000,
        "description": "Todos os recursos, sem limites de contas ou produtos.",
        "inherits": "basico",
        "features": [
            {
                "group": "Gestão",
                "name": "Análise financeira com filtro por período",
                "available": False,
            },
            {"group": "Gestão", "name": "Cadastro de fornecedores", "available": True},
            {
                "group": "Compras",
                "name": "Pedidos de compra: Pendente → Recebido",
                "available": False,
            },
            {"group": "Estoque", "name": "Cobertura de estoque em dias", "available": False},
            {"group": "Estoque", "name": "Movimentação em lote", "available": False},
            {"group": "Custos", "name": "Custo médio ponderado", "available": False},
            {"group": "Estoque", "name": "Histórico completo de cada item", "available": False},
            {"group": "Relatórios", "name": "Exportação Excel e PDF", "available": False},
            {"group": "Estoque", "name": "Validade por lote e saída FEFO", "available": False},
            {
                "group": "Atendimento",
                "name": "Suporte prioritário via WhatsApp",
                "available": False,
            },
            {"group": "Multiempresa", "name": "Empresas com dados isolados", "available": False},
            {
                "group": "Multiempresa",
                "name": "Transferências entre filiais com confirmação",
                "available": False,
            },
            {"group": "Multiempresa", "name": "Múltiplos locais de estoque", "available": False},
            {
                "group": "Multiempresa",
                "name": "Múltiplos pontos de atendimento",
                "available": False,
            },
            {
                "group": "Automação sem IA paga",
                "name": "Sugestões de compra por regras locais",
                "available": False,
            },
            {
                "group": "Automação sem IA paga",
                "name": "Importação por XML da NF-e",
                "available": False,
            },
            {"group": "Automação sem IA paga", "name": "Curva ABC automática", "available": False},
            {
                "group": "Automação sem IA paga",
                "name": "Resumo executivo diário",
                "available": False,
            },
            {
                "group": "Equipe e segurança",
                "name": "Admin Master e gestão de usuários",
                "available": False,
            },
            {
                "group": "Equipe e segurança",
                "name": "Permissões Membro, Admin e Master",
                "available": False,
            },
            {
                "group": "Equipe e segurança",
                "name": "Auditoria completa por usuário",
                "available": False,
            },
            {
                "group": "Equipe e segurança",
                "name": "Sincronização em tempo real",
                "available": False,
            },
            {
                "group": "Avançado",
                "name": "Código de barras no cadastro e movimentação",
                "available": False,
            },
            {
                "group": "Avançado",
                "name": "Exportação ABC e sugestões em PDF/Excel",
                "available": False,
            },
            {
                "group": "Avançado",
                "name": "Notificações de transferência em tempo real",
                "available": False,
            },
            {
                "group": "Atendimento",
                "name": "WhatsApp premium e onboarding personalizado gratuito",
                "available": False,
            },
            {
                "group": "Financeiro",
                "name": "Contas a pagar, receber e fluxo de caixa",
                "available": False,
            },
            {
                "group": "Financeiro",
                "name": "NF-e gera conta a pagar automaticamente",
                "available": False,
            },
            {
                "group": "Compras",
                "name": "Pedido em um clique e compartilhamento por WhatsApp",
                "available": False,
            },
            {
                "group": "Compras",
                "name": "Cotação com até 3 fornecedores e histórico de preços",
                "available": False,
            },
            {
                "group": "Estoque",
                "name": "Inventário cíclico com leitor e contagem cega",
                "available": False,
            },
            {
                "group": "Estoque",
                "name": "Impressão de etiquetas de código de barras",
                "available": False,
            },
            {"group": "Marca", "name": "Logo do negócio em relatórios e PDFs", "available": False},
            {
                "group": "Executivo",
                "name": "Resumo mensal em PDF e semanal por WhatsApp",
                "available": False,
            },
        ],
        "billing_options": [
            {"id": "mensal", "months": 1, "total_cents": 15000, "early_cancellation_months": None},
            {"id": "semestral", "months": 6, "total_cents": 75000, "early_cancellation_months": 2},
            {"id": "anual", "months": 12, "total_cents": 150000, "early_cancellation_months": 3},
        ],
    },
]
