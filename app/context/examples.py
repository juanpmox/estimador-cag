"""
Contexto estatico (CAG) que se inyecta en cada llamada al LLM.

Estos ejemplos funcionan como few-shot examples: representan estimaciones
previas ya realizadas, que sirven de referencia de estilo, nivel de detalle
y criterio para que el modelo genere nuevas estimaciones consistentes.

No hay base de datos ni retrieval: toda la "memoria" del sistema vive aqui,
como texto plano, y viaja completa en cada peticion al LLM.
"""

ESTIMATION_EXAMPLES = [
    {
        "meeting_summary": (
            "El cliente necesita una plataforma web de gestion de inventario "
            "para una pyme de distribucion. Debe permitir dar de alta productos, "
            "controlar stock por deposito, generar alertas de stock minimo y "
            "mostrar un dashboard con metricas basicas de rotacion. No requiere "
            "integracion con sistemas externos en esta primera fase."
        ),
        "estimation": """
## Estimacion: Plataforma de Gestion de Inventario

### Desglose de tareas:
1. Diseno UI/UX (wireframes + mockups): 40 horas
2. Backend API (CRUD productos, depositos, stock): 60 horas
3. Autenticacion y roles (admin / operador): 20 horas
4. Sistema de alertas de stock minimo: 15 horas
5. Dashboard con metricas de rotacion: 30 horas
6. Testing y QA: 25 horas

**Total estimado: 190 horas**
**Equipo recomendado: 2 desarrolladores full-stack + 1 disenador UX (part-time)**
**Duracion estimada: 6-8 semanas**
""",
    },
    {
        "meeting_summary": (
            "En la reunion, el equipo de marketing explico que necesita un "
            "microsite de campana con landing page, formulario de captacion de "
            "leads integrado con su CRM (Salesforce), y una seccion de "
            "preguntas frecuentes editable por el equipo de contenidos. El "
            "diseno visual ya esta definido por la agencia externa."
        ),
        "estimation": """
## Estimacion: Microsite de Campana con Integracion CRM

### Desglose de tareas:
1. Maquetado de landing page (a partir de diseno existente): 20 horas
2. Formulario de captacion + validaciones: 12 horas
3. Integracion API con Salesforce (leads): 25 horas
4. CMS ligero para seccion de FAQs: 18 horas
5. Optimizacion SEO y performance basica: 10 horas
6. Testing cross-browser y QA: 15 horas

**Total estimado: 100 horas**
**Equipo recomendado: 1 desarrollador frontend + 1 desarrollador backend (part-time)**
**Duracion estimada: 3-4 semanas**
""",
    },
]


def get_examples_as_text() -> str:
    """
    Serializa los ejemplos de contexto a texto plano, listo para ser
    inyectado dentro del system prompt.
    """
    blocks = []
    for i, example in enumerate(ESTIMATION_EXAMPLES, start=1):
        blocks.append(
            f"### Ejemplo {i}\n"
            f"**Resumen de la reunion:**\n{example['meeting_summary'].strip()}\n\n"
            f"**Estimacion generada:**\n{example['estimation'].strip()}"
        )
    return "\n\n---\n\n".join(blocks)
