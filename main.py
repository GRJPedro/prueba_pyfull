from datetime import date
from flask import Blueprint, Flask, request 
from flask_sqlalchemy import SQLAlchemy
from http import HTTPStatus

from dotenv import load_dotenv
import os

from marshmallow import Schema, fields, ValidationError, validates, validate
from psycopg2 import DataError, OperationalError
from sqlalchemy.exc import IntegrityError, InvalidRequestError

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')

db = SQLAlchemy(app)

persona_bp = Blueprint('persona_bp', __name__, url_prefix='/Persona')

class Persona(db.Model):
    __tablename__ = 'personas'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    apellido = db.Column(db.String(120), nullable=False)
    categoria = db.Column(db.String(120), nullable=False)
    edad = db.Column(db.Integer, nullable=True)
    correo_electronico = db.Column(db.String(120), nullable=False)
    url = db.Column(db.String(120), nullable=False)
    fecha_nacimiento = db.Column(db.Date, nullable=True)
    es_activo = db.Column(db.Boolean, default=True)


class PersonaSchema(Schema):
    #id = fields.Integer()
    nombre = fields.String(
        required=True,
        validate=[
            validate.Regexp(r'^[A-Za-z\s]+$',
                            error="El nombre solo puede contener letras y espacios."),
            validate.Length(min=2, max=120, 
                            error="El nombre debe tener entre 2 y 120 caracteres.")
        ]
    )
    apellido = fields.String(required=True)
    categoria = fields.String(
        required=True,
        validate=[
            validate.OneOf(
                ["estudiante", "profesor", "administrativo"],
                error="La categoría debe ser 'estudiante', 'profesor' o 'administrativo'."
            )
        ]
    )
    edad = fields.Integer(
        required=False,
        validate=[
            validate.Range(min=18, max=50, error="La edad debe estar entre 18 y 50 años."),
        ]
    )
    correo_electronico = fields.Email(required=True)
    url = fields.URL(required=True)

    fecha_nacimiento = fields.Date(
        required=False,
        validate=[
            validate.Range(
                min=date(1970, 1, 1),
                max=date(2005, 12, 31),
                error="La fecha de nacimiento debe estar entre el 1 de enero de 1970 y el 31 de diciembre de 2005."
            )
        ]
    )
    

    #es_activo = fields.Boolean()
    @validates("correo_electronico")
    def validate_correo_electronico(self, value, **kwargs):
        persona = Persona.query.filter_by(correo_electronico=value).first()
        if persona:
            raise ValidationError("El correo electrónico ya está registrado.")  

persona_schema = PersonaSchema()

@persona_bp.post('')
def crear_persona():

    try:
        data = persona_schema.load(request.json)
    except ValidationError as e:
        return e.messages, HTTPStatus.BAD_REQUEST
    
    
    
    persona = Persona(**data)

    try:
        db.session.add(persona)
        db.session.commit()
        
        return persona_schema.dump(persona), HTTPStatus.CREATED
    
    except IntegrityError:
        db.session.rollback()
        return {"error": "Violación de restricciones de integridad."}, HTTPStatus.CONFLICT
    except DataError:
        db.session.rollback()
        return {"error": "Error de datos."}, HTTPStatus.BAD_REQUEST
    except OperationalError:
        db.session.rollback()
        return {"error": "Error operativo."}, HTTPStatus.SERVICE_UNAVAILABLE
    finally:
        db.session.close()
    

@persona_bp.post("/bulk")
def crear_personas_bulk():
    try:
        data = persona_schema.load(request.json, many=True)
    except ValidationError as e:
        return e.messages, HTTPStatus.BAD_REQUEST
    

    lista_personas = []
    
    for persona_data in data:
        lista_personas.append(Persona(**persona_data))

    db.session.add_all(lista_personas)
    db.session.commit()

    return persona_schema.dump(lista_personas, many=True), HTTPStatus.CREATED

@persona_bp.get('')
def get_all_personas():
    print(dict(request.args))
    
    try:
        personas = Persona.query.filter_by(**request.args).all()
    except InvalidRequestError as e:
        return {"error": str(e)}

    return persona_schema.dump(personas, many=True), HTTPStatus.OK

#este endpoint es para obtener una persona por su id, se hace una consulta a la base de datos y se devuelve la persona si existe, si no existe se devuelve un mensaje de error
@persona_bp.get('/<int:id>')
def get_persona_by_id(id: int): #path param que es un parametro que se pasa en la url, en este caso el id de la persona
    persona = Persona.query.get(id)
    if not persona:
        return {"error": f"Persona con el id {id} no encontrada valedor"}, HTTPStatus.NOT_FOUND
    return persona_schema.dump(persona), HTTPStatus.OK

@persona_bp.put('/<int:id>')
def actualizar_persona(id: int):

    try:
        #valdar entrada
        data = persona_schema.load(request.json, partial=True) #partial=True para que no sea necesario enviar todos los campos, solo los que se quieren actualizar
    except ValidationError as e:
        return e.messages, HTTPStatus.BAD_REQUEST

    #consultar registro en base de datos
    persona = Persona.query.get_or_404(id, description=f"Persona con el id {id} no encontrada flaco")

    #este for sustituye a cada una las asiganciones para cada campo, revisar el codigo de respaldo putperso
    for key, value in data.items():
        setattr(persona, key, value)

    #actualizar cada campo

    db.session.commit()
    return persona_schema.dump(persona), HTTPStatus.OK

@persona_bp.delete('/<int:id>')
def eliminar_persona(id: int):
    persona = Persona.query.get_or_404(id, description=f"Persona con el id {id} no encontrada broder")
    db.session.delete(persona)
    db.session.commit()
    return '', HTTPStatus.NO_CONTENT

#es un error personalizado que devuelve un json
@persona_bp.errorhandler(404)
def not_found(e):
    return {"error": "Recurso no encontrado camarada"}, HTTPStatus.NOT_FOUND

app.register_blueprint(persona_bp)

with app.app_context():
    db.create_all()

app.run(debug=True)
