# Contrato: `crediagil.extraction`

## `crediagil.extraction.schemas`

```python
class CampoExtraido(BaseModel, Generic[T]):   # extra="forbid"
    valor: T
    fragmento: str                              # min_length=1

class CertificadoLaboral(BaseModel):  tipo: Literal["certificado_laboral"]; ...
class ExtractoBancario(BaseModel):    tipo: Literal["extracto_bancario"]; ...
class DocumentoNoSoportado(BaseModel): tipo: Literal["no_soportado"]; tipo_detectado: str  # no vacío ni solo espacios

Documento = Annotated[CertificadoLaboral | ExtractoBancario | DocumentoNoSoportado,
                      Field(discriminator="tipo")]

def validar_documento(datos: dict, texto: str) -> CertificadoLaboral | ExtractoBancario | DocumentoNoSoportado
```

Campos por tipo en [data-model.md](../data-model.md#documentos-unión-discriminada-por-tipo). `validar_documento`
usa `context={"texto": texto}`; los modelos fallan si se validan sin ese contexto y tienen
campos con fragmento.

| Caso | Entrada | Resultado |
|------|---------|-----------|
| Campo completo y literal | `{"valor": 2500000, "fragmento": "salario de $2.500.000"}` presente en el texto | válido |
| Sin fragmento | `{"valor": 2500000}` | `ValidationError` (campo) |
| Fragmento vacío o solo espacios | `{"valor": 2500000, "fragmento": "   "}` | `ValidationError` |
| Salario o abono ≤ 0, booleano o texto | `{"valor": 0, …}` / `{"valor": True, …}` / `{"valor": "2500000", …}` | `ValidationError` |
| Fragmento no literal | fragmento con un espacio de más o distinta mayúscula | `ValidationError` indicando el campo |
| Campo ausente | `salario_mensual: None` | válido; dato faltante |
| Campo extra | `{"valor":…, "fragmento":…, "confianza": 0.9}` | `ValidationError` |
| Tipo desconocido | `{"tipo": "pasaporte"}` | `ValidationError` (el extractor debe usar `no_soportado`) |
| Sin contexto | `CertificadoLaboral.model_validate(datos)` con campos | `ValidationError` ("falta el texto del documento") |

## `crediagil.extraction.income`

```python
class TipoHallazgo(StrEnum): DATO_FALTANTE, INCONSISTENCIA_DOCUMENTAL, FUERA_DE_POLITICA

@dataclass(frozen=True)
class Hallazgo: tipo: TipoHallazgo; mensaje: str; campo: str | None = None; regla: str = "ingreso"
# regla: la del Motivo al convertirlo en Resultado ("ingreso", "moneda", "documento", "nomina")

@dataclass(frozen=True)
class IngresoVerificado: valor: int; moneda: str; origen: CampoExtraido[int]

@dataclass(frozen=True)
class ResultadoIngreso: ingreso: IngresoVerificado | None; hallazgos: list[Hallazgo]

def derivar_ingreso(documentos: list[Documento]) -> ResultadoIngreso
def resultado_de_hallazgos(r: ResultadoIngreso) -> Resultado   # puente a crediagil.policy
```

| Caso | Documentos | `ingreso` | Hallazgos |
|------|------------|-----------|-----------|
| Certificado con salario COP | cert(2.000.000) | 2.000.000, origen = campo salario | — |
| Sin certificado | extractos con nómina | `None` | `DATO_FALTANTE` (`salario_mensual`) |
| Certificado sin salario | cert(salario=None) + extractos | `None` | `DATO_FALTANTE`; no usa extractos |
| Moneda USD | cert(moneda="USD") | `None` | `FUERA_DE_POLITICA` (moneda) |
| Certificado sin moneda | cert(moneda=None) | `None` | `DATO_FALTANTE` (`moneda`); no se asume COP |
| Extracto en otra moneda | cert + extracto(moneda="USD") | según cert | `FUERA_DE_POLITICA`; ese extracto no entra en el promedio de nómina |
| Documento no soportado | `no_soportado` + cert | según cert | `FUERA_DE_POLITICA` (documento) |
| Nómina 10% exacto | cert(2.000.000) + nómina promedio 2.200.000 | 2.000.000 | — |
| Nómina > 10% | promedio 2.200.001 o 1.799.999 | 2.000.000 | `INCONSISTENCIA_DOCUMENTAL` |
| Sin abonos de nómina | cert + extracto sin nómina | 2.000.000 | — (no se evalúa) |
| Nómina justo bajo 10% | promedio 2.199.999 o 1.800.001 | 2.000.000 | — |
| Varios certificados, salarios distintos | cert(2.000.000) + cert(2.500.000) | `None` | `DATO_FALTANTE` (`salario_mensual`, ambiguo) |
| Varios certificados, mismo salario | cert(2.000.000) ×2 | 2.000.000 | — |
| Varios certificados, mismo salario, uno en USD (cualquier orden) | cert(COP) + cert(USD) | `None` | `FUERA_DE_POLITICA` (moneda) |
| Varios certificados, mismo salario, uno sin moneda (cualquier orden) | cert(COP) + cert(moneda=None) | `None` | `DATO_FALTANTE` (`moneda`) |
| Salarios distintos, uno en USD (cualquier orden) | cert(COP, 2.000.000) + cert(USD, 3.000) | `None` | `FUERA_DE_POLITICA` (moneda) + `DATO_FALTANTE` (ambiguo); decisión fuera de política |
| Certificado en USD sin salario | cert(USD, salario=None) | `None` | `FUERA_DE_POLITICA` (moneda) + `DATO_FALTANTE` (`salario_mensual`) |
| Extracto sin moneda | cert + extracto(moneda=None, abonos 9.000.000) | 2.000.000 | — (sus abonos no entran en el promedio) |
| Extracto USD con nómina distinta | cert + extracto(USD, abonos 9.000.000) | 2.000.000 | solo `FUERA_DE_POLITICA` (sin inconsistencia) |

Con varios certificados se acumulan **todos** los hallazgos (otra moneda, moneda faltante, salario ambiguo, sin salario); si hay alguno, no hay ingreso verificado. El resultado no depende del orden.

`resultado_de_hallazgos`: algún `FUERA_DE_POLITICA` → `FUERA_DE_POLITICA`; algún otro hallazgo
→ `ANALISTA`; ninguno → `PREAPROBABLE` (sin motivos).
