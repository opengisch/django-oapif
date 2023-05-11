use flatgeobuf::{FallibleStreamingIterator, FgbReader, FgbWriter, GeometryType};
use geozero::{
    error::GeozeroError, geojson::GeoJsonReader, wkt::WktReader, GeozeroDatasource, ToJson, ToWkt,
};
use pyo3::{
    exceptions::PyTypeError,
    prelude::*,
    types::{PyBytes, PyUnicode},
};
use std::io::Cursor;

fn decode(bytes: &[u8], format: &PyUnicode) -> Result<Vec<String>, geozero::error::GeozeroError> {
    /* Decode utf-8 string bytes to JSON object */
    let mut buff = Cursor::new(bytes);
    let fgb = FgbReader::open(&mut buff)?.select_all()?;
    let mut results = Vec::<String>::new();
    match format.to_str().unwrap() {
        "geojson" => fgb.for_each(|item| {
            let res = item.to_json().unwrap();
            results.push(res);
        }),
        "wkt" => fgb.for_each(|item| {
            let res = item.to_wkt().unwrap();
            results.push(res);
        }),
        _ => {
            return Err(GeozeroError::Geometry(
                "Feature format could not be determined!".to_string(),
            ));
        }
    }?;
    Ok(results)
}

fn encode(
    bytes: &[u8],
    py_geometry: &PyUnicode,
    format: &PyUnicode,
) -> Result<Vec<u8>, geozero::error::GeozeroError> {
    /* Encode utf-8 JSON bytes to FGB bytes */
    let geometry = py_geometry.to_str().unwrap();
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
    let mut fgb = FgbWriter::create("tmp", geometry_type)?;
    match format.to_str().unwrap() {
        "geojson" => {
            let mut r = GeoJsonReader(&mut buff);
            r.process(&mut fgb)?;
        }
        "wkt" => {
            let mut r = WktReader(&mut buff);
            r.process(&mut fgb)?;
        }
        _ => {
            return Err(GeozeroError::Geometry(
                "Feature format could not be determined!".to_string(),
            ))
        }
    };
    fgb.write(&mut results)?;
    Ok(results)
}

#[pyfunction]
fn from_fgb(pybytes: &PyBytes, format: &PyUnicode) -> PyResult<Vec<String>> {
    /* Try decoding FGB bytes to WKT or JSON string */
    let bytes = pybytes.as_bytes();
    match decode(bytes, format) {
        Ok(res) => Ok(res),
        Err(error) => Err(PyErr::new::<PyTypeError, _>(error.to_string())),
    }
}

#[pyfunction]
fn to_fgb(pybytes: &PyBytes, geometry: &PyUnicode, format: &PyUnicode) -> PyResult<Vec<u8>> {
    /* Try encoding JSON or WKT bytes to FGB */
    let bytes = pybytes.as_bytes();
    match encode(bytes, geometry, format) {
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
