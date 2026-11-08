# Educar para Transformar — sistema visual

## Referencia elegida

La referencia principal es **Airbnb**, a partir del análisis `design-md/airbnb/DESIGN.md` del repositorio [VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md). Se toma su superficie clara, el uso generoso de fotografía, las tarjetas amables y las formas redondeadas. Es una base adecuada para una comunidad educativa: da prioridad a las personas, los espacios y la lectura.

La adaptación conserva los colores que ya identifican a Educar para Transformar. El azul organiza la navegación y las acciones principales; el verde y el rosa se reservan para acentos y estados. No se replica el rojo Rausch ni la marca de Airbnb.

Se compararon las referencias solicitadas:

- **Linear**: jerarquía tipográfica precisa y superficies sobrias; su tratamiento oscuro y denso corresponde más a una herramienta de trabajo que a un sitio escolar.
- **Vercel**: alto contraste monocromático, geometría y gradientes; es expresivo para una plataforma de desarrollo, pero menos cercano a la identidad cálida del instituto.
- **Stripe**: índigo, malla de gradientes y lenguaje financiero; su personalidad de producto comercial no acompaña el logo multicolor del centro.
- **Airbnb**: fotografía, superficies blancas, interacción suave y geometría redondeada; coincide mejor con las imágenes institucionales y con una experiencia accesible para estudiantes y familias.

La biblioteca **21st.dev** se consultó para revisar composiciones reales de paneles, métricas, navegación y tarjetas. Se adapta el patrón de shell con navegación, tarjetas de métricas y tablas, sin copiar componentes React/Tailwind ni introducir frameworks en Django. Para listas administrativas, las tablas conservan columnas alineadas, y las tarjetas quedan para resúmenes breves.

## Atribución y fuentes

- Sistema visual de referencia: [VoltAgent/awesome-design-md — Airbnb](https://github.com/VoltAgent/awesome-design-md/blob/main/design-md/airbnb/DESIGN.md).
- Comparaciones: [Linear](https://github.com/VoltAgent/awesome-design-md/blob/main/design-md/linear.app/DESIGN.md), [Vercel](https://raw.githubusercontent.com/VoltAgent/awesome-design-md/main/design-md/vercel/DESIGN.md) y [Stripe](https://github.com/abhayjnayakk/awesome-design-md/blob/main/upstream/voltagent-awesome-design-md/design-md/stripe/DESIGN.md), copia del material upstream cuando la carpeta original redirige el contenido.
- Guías de interfaz y skill: [web-interface-guidelines](https://github.com/vercel-labs/web-interface-guidelines) y [web-design-guidelines](https://github.com/vercel-labs/agent-skills/tree/main/skills/web-design-guidelines).
- Patrones de componentes: [21st.dev — dashboards](https://21st.dev/community/components/explore/dashboard-component) y [21st.dev — tarjetas](https://preview.21st.dev/%40wensity/components/card).
- Tipografía redondeada preferida: [Centrale Sans Rounded, de Typedepot en MyFonts](https://www.myfonts.com/collections/centrale-sans-rounded-font-typedepot). La familia comercial no se distribuye aquí. Si no está instalada, los títulos usan Nunito local como alternativa redondeada. Nunito se distribuye con la licencia OFL y su licencia acompaña el archivo de fuente.

## Tokens

### Color

| Token | Valor | Uso |
| --- | --- | --- |
| `ink` | `#18324B` | Títulos, datos importantes y texto de alto contraste |
| `text` | `#344C62` | Texto general |
| `muted` | `#62758A` | Ayuda, metadatos y descripciones |
| `canvas` | `#F6F9FC` | Fondo general |
| `surface` | `#FFFFFF` | Formularios, tarjetas y paneles |
| `border` | `#DCE6EF` | Separadores y bordes |
| `brand-blue` | `#1D66C2` | Identidad y enlaces |
| `action-blue` | `#17569F` | Botones primarios y estados activos |
| `blue-soft` | `#E8F2FF` | Selección y fondos secundarios |
| `green` | `#4C7A2E` | Acciones y estados positivos |
| `green-soft` | `#EDF6E7` | Fondo de estado positivo |
| `pink` | `#B91D6A` | Acento y estados de atención |
| `pink-soft` | `#FCEBF4` | Fondo de error o atención |

El logotipo conserva sus tonos originales. Los tonos oscuros de interacción mejoran el contraste de texto; los tonos intensos del logo se mantienen en detalles gráficos.

### Tipografía

- **Títulos y marca**: `Centrale Sans Rounded`, peso 700 (estilo Bold). Fallback: `Nunito`, `Trebuchet MS`, Arial.
- **Texto largo y formularios**: Arial/Helvetica para lectura clara y consistente.
- **Uso acotado de Nunito**: alternativa para títulos si Centrale no está instalada, además de subtítulos, botones y algunos rótulos. No se aplica a todo el cuerpo.
- **Escala**: título principal fluido de 32–58 px; sección 24–32 px; tarjeta 18–20 px; cuerpo 16 px; ayuda 13–14 px.
- Mantener interlineado de 1.5 o superior en texto largo. Usar peso 700 solo para títulos, acciones y etiquetas.

> La CSS declara Centrale como primera opción, pero el proyecto no incluye el archivo comercial. Para que aparezca exactamente en todos los despliegues, hace falta una licencia web y su WOFF/WOFF2 local. No cargarla desde un CDN.

### Espaciado, bordes y profundidad

- Base de espaciado: 4 px; escala habitual: 4, 8, 12, 16, 24, 32, 48 y 64 px.
- Radios: 10 px para controles, 16 px para tarjetas, 22 px para paneles y píldora para acciones de énfasis.
- Fondos claros con bordes suaves; sombra baja en tarjetas y una sombra más marcada solo en diálogos.
- Evitar gradientes fuertes y sombras grandes. Usar los tonos del logo en pequeñas áreas, no como fondos extensos detrás de texto.

### Componentes

- **Cabecera**: logo de 88 px de ancho (74 px en móvil), nombre institucional legible, navegación con enlaces de al menos 42 px de alto y acceso destacado.
- **Acciones**: azul oscuro para la acción principal; botones secundarios claros y claramente distinguibles. Hover y foco aumentan contraste.
- **Tarjetas**: borde fino, separación uniforme, contenido alineado y altura determinada por el contenido. Mantener el acento azul/verde/rosa en bloques suaves.
- **Paneles de rol**: navegación a la izquierda en escritorio; en móvil pasa a una franja desplazable. Métricas en tarjetas; datos detallados en tablas con desplazamiento horizontal cuando lo necesiten.
- **Formularios**: etiqueta visible sobre el control, altura mínima de 44 px, error junto al campo y estado de foco de 3 px. Conservar nombres, método, CSRF y validación Django.
- **Carruseles y modales**: controles con nombre accesible, alternativas por teclado y controles visibles; el movimiento automático se detiene con `prefers-reduced-motion` y tiene pausa explícita.
- **Estados**: colores con texto y significado, nunca solo color. Mensajes de error indican el campo o corrección disponible cuando el backend la proporcione.

### Adaptación

- Escritorio: contenido limitado a 1280 px, panel lateral fijo en paneles de rol.
- Tableta: tarjetas en dos columnas; barra lateral pasa arriba y permite desplazamiento horizontal.
- Móvil: una columna para tarjetas y formularios; espacios laterales compactos; tablas y menús anchos pueden desplazarse horizontalmente sin deformar sus datos.
- Mantener visible el foco y evitar que cabeceras, modales o controles tapen el elemento enfocado.

### Accesibilidad y movimiento

- HTML semántico; enlace “Saltar al contenido” antes de la navegación y destino `main` enfocable.
- Todos los enlaces, botones y campos muestran `:focus-visible`.
- Controles de icono con `aria-label`; imágenes informativas con `alt`, decorativas con `alt=""`.
- No eliminar zoom. No usar `transition: all`; animar solo color, opacidad y transform.
- Respetar `prefers-reduced-motion`. El contenido administrativo permanece legible sin depender de animación, hover ni estados de color.
