use flatgeobuf::{FallibleStreamingIterator, FgbReader, FgbWriter, GeometryType};
use geozero::{error::GeozeroError, geojson::GeoJsonReader, GeozeroDatasource, ToJson};
use pyo3::{
    exceptions::PyTypeError,
    prelude::*,
    types::{PyBytes, PyUnicode},
};
use std::io::Cursor;

fn decode(bytes: &[u8]) -> Result<Vec<String>, geozero::error::GeozeroError> {
    /* Decode utf-8 string bytes to JSON object */
    let mut buff = Cursor::new(bytes);
    let mut fgb = FgbReader::open(&mut buff)?.select_all()?;

    // Reading and collecting results
    let mut results = Vec::<String>::new();
    while let Some(feature) = fgb.next()? {
        match feature.to_json() {
            Ok(res) => results.push(res),
            Err(msg) => return Err(msg),
        }
    }
    Ok(results)
}

fn encode(bytes: &[u8], py_geometry: &PyUnicode) -> Result<Vec<u8>, geozero::error::GeozeroError> {
    /* Encode utf-8 JSON bytes to FGB bytes */
    if let Ok(geometry) = py_geometry.to_str() {
        let geometry_type = match geometry {
            "geometry_collection" => GeometryType::GeometryCollection,
            "circular_string" => GeometryType::CircularString,
            "compound_curve" => GeometryType::CompoundCurve,
            "curve" => GeometryType::Curve,
            "curve_polygon" => GeometryType::CurvePolygon,
            "line_string" => GeometryType::LineString,
            "multi_curve" => GeometryType::MultiCurve,
            "multi_polygon" => GeometryType::MultiPolygon,
            "multi_point" => GeometryType::MultiPoint,
            "multi_surface" => GeometryType::MultiSurface,
            "multiline_string" => GeometryType::MultiLineString,
            "point" => GeometryType::Point,
            "polygon" => GeometryType::Polygon,
            "polyhedral_surface" => GeometryType::PolyhedralSurface,
            "surface" => GeometryType::Surface,
            "tin" => GeometryType::TIN,
            "triangle" => GeometryType::Triangle,
            _ => {
                return Err(GeozeroError::Geometry(
                    "Geometry type could not be determined!".to_string(),
                ))
            }
        };
        let mut results = Vec::<u8>::new();
        let mut buff = Cursor::new(bytes);
        let mut reader = GeoJsonReader(&mut buff);
        let mut fgb = FgbWriter::create("tmp", geometry_type)?;
        reader.process(&mut fgb)?;
        fgb.write(&mut results)?;
        Ok(results)
    } else {
        Err(GeozeroError::Geometry(
            "Geometry type could not be determined!".to_string(),
        ))
    }
}

#[pyfunction]
fn from_fgb(pybytes: &PyBytes) -> PyResult<Vec<String>> {
    /* Try decoding FGB bytes to a JSON string */
    let bytes = pybytes.as_bytes();
    match decode(bytes) {
        Ok(res) => Ok(res),
        Err(error) => Err(PyErr::new::<PyTypeError, _>(error.to_string())),
    }
}

#[pyfunction]
fn to_fgb(pybytes: &PyBytes, geometry: &PyUnicode) -> PyResult<Vec<u8>> {
    /* Try encoding JSON bytes to FGB */
    let bytes = pybytes.to_owned().as_bytes();
    match encode(bytes, geometry) {
        Ok(res) => Ok(res),
        Err(error) => Err(PyErr::new::<PyTypeError, _>(error.to_string())),
    }
}

#[pymodule]
fn flatgeobuf_pyrust(_py: Python, m: &PyModule) -> PyResult<()> {
    /* Registers `from_fgb` to package namespace `flatgeobuf_pyrust` */
    m.add_function(wrap_pyfunction!(from_fgb, m)?)?;
    m.add_function(wrap_pyfunction!(to_fgb, m)?)?;
    Ok(())
}
