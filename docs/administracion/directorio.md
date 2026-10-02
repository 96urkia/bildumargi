# Directorio de bibliotecas

El fichero `bibliotecas.xlsx` es lo que permite a Bildumargi reconocer qué
biblioteca ha subido los listados y con qué población comparar su colección.
Está en la carpeta de datos (`datos/` en el zip, `/var/lib/bildumargi` en el
servidor).

## Columnas

| Columna | ¿Obligatoria? | Qué es |
|---|---|---|
| `Nombre_biblioteca` | Sí | El nombre tal como aparece en el campo 952 del catálogo. |
| `Sucursal` | Sí | El número de la columna «Suc.» de los listados de AbsysNet. |
| `Poblacion` | Sí | Habitantes atendidos. |
| `Metros_cuadrados` | No | Superficie útil. Sin ella, el indicador por m² sale como «N/D». |
| `Clave` | No | Clave para [entrar con clave](../uso/entrar-con-clave.md). |

El fichero trae tres filas de ejemplo: **bórralas** y escribe tus bibliotecas
debajo, una por fila, sin tocar la primera fila. Cada cabecera lleva un
comentario y la segunda hoja repite las instrucciones.

**El código de sucursal** está en la columna «Suc.» de cualquier topográfico
exportado de AbsysNet: es el mismo en todas las líneas de una biblioteca.

## Claves de acceso

Las claves las crea y las cambia **la administración de la red** en la
columna `Clave`. No hay registro de usuarios ni recuperación por correo: quien
la olvide pide otra. Bildumargi relee el Excel al momento, sin reiniciar.

Para que el acceso con clave funcione, además, el **historial de cargas** debe
estar activo en la [Administración de la red](panel-red.md).

!!! danger "Las claves se guardan sin cifrar"
    Es una barrera sencilla, no un sistema de seguridad. Usa claves que no
    sirvan para nada más y **no compartas ni publiques** el Excel con las
    claves puestas. En particular, no lo subas a ningún repositorio.

## Formato CSV

Si no usas Excel, guarda lo mismo como `bibliotecas.csv` con esas columnas en
la primera fila.
