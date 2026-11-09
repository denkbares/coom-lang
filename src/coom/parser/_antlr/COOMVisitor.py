# Generated from /var/folders/6t/xjsbv5k929s9vkvtz4c0wbcm0000gn/T/tmpthw5uwls/COOM.g4 by ANTLR 4.13.2
from antlr4 import *
if "." in __name__:
    from .COOMParser import COOMParser
else:
    from COOMParser import COOMParser

# This class defines a complete generic visitor for a parse tree produced by COOMParser.

class COOMVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by COOMParser#model.
    def visitModel(self, ctx:COOMParser.ModelContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#product.
    def visitProduct(self, ctx:COOMParser.ProductContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#structure.
    def visitStructure(self, ctx:COOMParser.StructureContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#enumeration.
    def visitEnumeration(self, ctx:COOMParser.EnumerationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#feature.
    def visitFeature(self, ctx:COOMParser.FeatureContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#cardinality.
    def visitCardinality(self, ctx:COOMParser.CardinalityContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#attribute.
    def visitAttribute(self, ctx:COOMParser.AttributeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#option.
    def visitOption(self, ctx:COOMParser.OptionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#field.
    def visitField(self, ctx:COOMParser.FieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#number_def.
    def visitNumber_def(self, ctx:COOMParser.Number_defContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#bound.
    def visitBound(self, ctx:COOMParser.BoundContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#string_def.
    def visitString_def(self, ctx:COOMParser.String_defContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#fraction.
    def visitFraction(self, ctx:COOMParser.FractionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#unit.
    def visitUnit(self, ctx:COOMParser.UnitContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#constant.
    def visitConstant(self, ctx:COOMParser.ConstantContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#floating.
    def visitFloating(self, ctx:COOMParser.FloatingContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#path.
    def visitPath(self, ctx:COOMParser.PathContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#path_item.
    def visitPath_item(self, ctx:COOMParser.Path_itemContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#path_index.
    def visitPath_index(self, ctx:COOMParser.Path_indexContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#name.
    def visitName(self, ctx:COOMParser.NameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#stmt_end.
    def visitStmt_end(self, ctx:COOMParser.Stmt_endContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#same_line.
    def visitSame_line(self, ctx:COOMParser.Same_lineContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#compare.
    def visitCompare(self, ctx:COOMParser.CompareContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#behavior.
    def visitBehavior(self, ctx:COOMParser.BehaviorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#behavior_block.
    def visitBehavior_block(self, ctx:COOMParser.Behavior_blockContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#define.
    def visitDefine(self, ctx:COOMParser.DefineContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#conditioned.
    def visitConditioned(self, ctx:COOMParser.ConditionedContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#explanation.
    def visitExplanation(self, ctx:COOMParser.ExplanationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#precondition.
    def visitPrecondition(self, ctx:COOMParser.PreconditionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#combinations.
    def visitCombinations(self, ctx:COOMParser.CombinationsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#combination_row.
    def visitCombination_row(self, ctx:COOMParser.Combination_rowContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#combination_item.
    def visitCombination_item(self, ctx:COOMParser.Combination_itemContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#combination_atom.
    def visitCombination_atom(self, ctx:COOMParser.Combination_atomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#derivation_table.
    def visitDerivation_table(self, ctx:COOMParser.Derivation_tableContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#derivation_table_columns.
    def visitDerivation_table_columns(self, ctx:COOMParser.Derivation_table_columnsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#derivation_table_row.
    def visitDerivation_table_row(self, ctx:COOMParser.Derivation_table_rowContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#derivation_condition_cell.
    def visitDerivation_condition_cell(self, ctx:COOMParser.Derivation_condition_cellContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#derivation_table_atom.
    def visitDerivation_table_atom(self, ctx:COOMParser.Derivation_table_atomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#assign_default.
    def visitAssign_default(self, ctx:COOMParser.Assign_defaultContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#assign_imply.
    def visitAssign_imply(self, ctx:COOMParser.Assign_implyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#optimize.
    def visitOptimize(self, ctx:COOMParser.OptimizeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#visibility.
    def visitVisibility(self, ctx:COOMParser.VisibilityContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#require.
    def visitRequire(self, ctx:COOMParser.RequireContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#formula.
    def visitFormula(self, ctx:COOMParser.FormulaContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#formula_add.
    def visitFormula_add(self, ctx:COOMParser.Formula_addContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#formula_mul.
    def visitFormula_mul(self, ctx:COOMParser.Formula_mulContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#formula_sign.
    def visitFormula_sign(self, ctx:COOMParser.Formula_signContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#formula_pow.
    def visitFormula_pow(self, ctx:COOMParser.Formula_powContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#formula_primary.
    def visitFormula_primary(self, ctx:COOMParser.Formula_primaryContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#formula_func.
    def visitFormula_func(self, ctx:COOMParser.Formula_funcContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#formula_atom.
    def visitFormula_atom(self, ctx:COOMParser.Formula_atomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#condition.
    def visitCondition(self, ctx:COOMParser.ConditionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#condition_or.
    def visitCondition_or(self, ctx:COOMParser.Condition_orContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#condition_and.
    def visitCondition_and(self, ctx:COOMParser.Condition_andContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#condition_not.
    def visitCondition_not(self, ctx:COOMParser.Condition_notContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#condition_compare.
    def visitCondition_compare(self, ctx:COOMParser.Condition_compareContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#condition_part.
    def visitCondition_part(self, ctx:COOMParser.Condition_partContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#test.
    def visitTest(self, ctx:COOMParser.TestContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#test_statement.
    def visitTest_statement(self, ctx:COOMParser.Test_statementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#test_set.
    def visitTest_set(self, ctx:COOMParser.Test_setContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#test_remove.
    def visitTest_remove(self, ctx:COOMParser.Test_removeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#test_reset.
    def visitTest_reset(self, ctx:COOMParser.Test_resetContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#test_fixed.
    def visitTest_fixed(self, ctx:COOMParser.Test_fixedContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#test_shown.
    def visitTest_shown(self, ctx:COOMParser.Test_shownContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#test_empty.
    def visitTest_empty(self, ctx:COOMParser.Test_emptyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#test_available.
    def visitTest_available(self, ctx:COOMParser.Test_availableContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by COOMParser#test_blocked.
    def visitTest_blocked(self, ctx:COOMParser.Test_blockedContext):
        return self.visitChildren(ctx)



del COOMParser