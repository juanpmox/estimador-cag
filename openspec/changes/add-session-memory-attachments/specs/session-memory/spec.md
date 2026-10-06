# Spec Delta

## Purpose

Mantiene el estado de una conversacion de estimacion (historial de mensajes y hechos del proyecto) a lo largo de varias peticiones encadenadas dentro de una misma sesion, para que el modelo no pierda el contexto del proyecto en curso entre turnos.

## ADDED Requirements

### Requirement: Creacion de sesiones
El sistema SHALL exponer `POST /api/v1/sessions`, que crea una sesion vacia en memoria del proceso y devuelve un identificador unico (`session_id`) en formato UUID v4.

#### Scenario: Crear una sesion nueva
- **WHEN** el cliente hace `POST /api/v1/sessions`
- **THEN** la respuesta es `200` con un cuerpo `{"session_id": "<uuid4>"}` y el `session_id` queda registrado en memoria del proceso

#### Scenario: Identificadores unicos
- **WHEN** el cliente crea dos sesiones distintas
- **THEN** los dos `session_id` devueltos son diferentes

### Requirement: Estimacion multi-turno sobre una sesion
El sistema SHALL exponer `POST /api/v1/sessions/{session_id}/estimate`, que acepta `multipart/form-data` con el campo `transcript` (texto) y una lista opcional de `attachments`, y devuelve una estimacion que respeta el contrato de estimacion existente.

#### Scenario: Estimacion sobre una sesion existente
- **WHEN** el cliente envia `POST /api/v1/sessions/{session_id}/estimate` con un `transcript` para un `session_id` valido
- **THEN** la respuesta es `200` con el texto de la estimacion, la version de prompt usada, el `session_id` y el `project_metadata` actualizado

#### Scenario: Sesion inexistente
- **WHEN** el cliente llama al endpoint de estimacion con un `session_id` que no existe
- **THEN** la respuesta es `404`

### Requirement: Historial con ventana deslizante
El sistema SHALL conservar por sesion el historial de mensajes (pares user+assistant) y SHALL mantener como maximo `MAX_TURNS` turnos; al superar el limite descarta los pares mas antiguos y preserva siempre el system prompt.

#### Scenario: Limite de la ventana
- **WHEN** una sesion recibe mas turnos que `MAX_TURNS`
- **THEN** el array de mensajes enviado al LLM nunca contiene mas de `MAX_TURNS` mensajes `assistant` correspondientes al historial conservado

#### Scenario: El system prompt no se descarta
- **WHEN** la ventana deslizante descarta turnos antiguos
- **THEN** el system prompt (regenerado desde el `project_metadata` actual) sigue presente como primer mensaje

### Requirement: project_metadata separado del historial
El sistema SHALL mantener por sesion un `project_metadata` (nombre del proyecto, tamano de equipo asumido, tecnologias mencionadas, alcance acordado) independiente del historial de mensajes, y SHALL inyectarlo en el system prompt dentro de un bloque `<project_metadata>`.

#### Scenario: Primera llamada sin hechos
- **WHEN** se estima en una sesion recien creada, sin hechos conocidos
- **THEN** el bloque `<project_metadata>` del system prompt esta presente pero vacio

#### Scenario: Inyeccion de hechos conocidos
- **WHEN** el `project_metadata` de la sesion ya tiene hechos (por ejemplo un nombre de proyecto)
- **THEN** esos hechos aparecen dentro del bloque `<project_metadata>` del system prompt renderizado

### Requirement: Actualizacion del project_metadata por turno
El sistema SHALL actualizar el `project_metadata` de la sesion al finalizar cada turno, extrayendo los hechos relevantes de la nueva interaccion, y SHALL devolverlo en la respuesta.

#### Scenario: Metadata se actualiza entre turnos
- **WHEN** una sesion recibe un turno que menciona nueva informacion del proyecto (por ejemplo su nombre o tecnologias)
- **THEN** el `project_metadata` devuelto en esa respuesta incluye esos hechos y persiste para el siguiente turno

#### Scenario: Coherencia entre turnos
- **WHEN** un turno posterior no repite el nombre del proyecto ya conocido
- **THEN** el nombre del proyecto sigue presente en el `project_metadata` de la sesion
