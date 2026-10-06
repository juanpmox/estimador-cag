# Spec Delta

## Purpose

Permite enriquecer la transcripcion de una estimacion con documentacion complementaria adjunta (PDFs y documentos Word), extrayendo su texto localmente en el servicio IA para incorporarlo al contexto del prompt.

## ADDED Requirements

### Requirement: Adjuntos en multipart/form-data
El endpoint de estimacion de una sesion SHALL aceptar en la misma peticion `multipart/form-data` el campo de texto `transcript` y una lista opcional de archivos `attachments`.

#### Scenario: Peticion con adjuntos
- **WHEN** el cliente envia `transcript` y uno o mas archivos en `attachments`
- **THEN** el servicio procesa la transcripcion y cada adjunto en una sola peticion

#### Scenario: Peticion sin adjuntos
- **WHEN** el cliente envia solo el campo `transcript`
- **THEN** el servicio genera la estimacion usando unicamente la transcripcion

### Requirement: Extraccion local de texto de adjuntos
El sistema SHALL extraer el texto de los adjuntos localmente: PDF con `pypdf` y documentos Word (`docx`) con `python-docx`, sin depender del proveedor LLM.

#### Scenario: Extraccion de PDF
- **WHEN** se adjunta un archivo `.pdf` con texto
- **THEN** el servicio obtiene el texto del documento mediante extraccion local

#### Scenario: Extraccion de Word
- **WHEN** se adjunta un archivo `.docx` con texto
- **THEN** el servicio obtiene el texto del documento mediante extraccion local

#### Scenario: Tipo no soportado
- **WHEN** se adjunta un archivo con una extension no soportada
- **THEN** el servicio responde con error (`400`) indicando que el tipo de adjunto no es valido

### Requirement: Incorporacion del adjunto al contexto
El sistema SHALL concatenar el texto extraido de cada adjunto a la transcripcion usando un separador explicito que incluye el nombre del archivo (`--- attachment: <nombre> ---`) antes de construir el prompt.

#### Scenario: El contenido del adjunto llega al prompt
- **WHEN** se adjunta un documento cuyo texto contiene una especificacion tecnica
- **THEN** el texto extraido del documento aparece en el mensaje enviado al LLM, precedido por su separador
