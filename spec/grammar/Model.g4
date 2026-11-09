// COOM language 1.0, a model file.
grammar Model;
import Structure, Behavior, Testing;

model : (product | structure | enumeration | behavior | test)* EOF ;
