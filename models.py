from sqlalchemy import create_engine, ForeignKey, Column, Integer, String, DateTime, Date, Time, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()

class Property(Base):
    __tablename__ = 'property'

    id = Column(Integer, primary_key = True)
    name = Column(String(255))
    address1 = Column(String(255))
    address2 = Column(String(255))
    address3 = Column(String(255))
    city = Column(String(255))
    state = Column(String(255))
    zipcode = Column(String(255))
    country = Column(String(255))

    def __repr__(self):
        return f'''<Property(name='{self.name}', city='{self.city}', state='{self.state}', zipcode='{self.zipcode}', country='{self.country}')>'''

class Transaction(Base):
    __tablename__ = 'transaction'

    id = Column(Integer, primary_key = True)
    datetime_created = Column(DateTime(timezone=True), server_default=func.now())
    property_id = Column(Integer, ForeignKey('property.id'))
    datetime_payment = Column(DateTime)
    name = Column(String(255))
    reference1 = Column(String(255))
    reference2 = Column(String(255))
    category_id = Column(Integer, ForeignKey('category.id'))
    amount = Column(Float)
    property_name = relationship('Property', foreign_keys=[property_id])
    category_name = relationship('Category', foreign_keys=[category_id])

    def __repr__(self):
        return f'''<Transaction(property='{self.property_name}', category='{self.category_name}', datetime_payment='{self.datetime_payment}', reference1='{self.reference1}', amount='{self.amount}')>'''

class Category(Base):
    __tablename__ = 'category'

    id = Column(Integer, primary_key = True)
    category = Column(String(255))
    description = Column(String(255))

    def __repr__(self):
        return f'''<Category(id='{self.id}', category='{self.category}', description='{self.description}')>'''

class User(Base):
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    email = Column(String(100), unique=True)
    password = Column(String(100))
    name = Column(String(1000))

    def __repr__(self):
        return f'''<User(id='{self.id}', email='{self.email}', name='{self.name}')>'''
