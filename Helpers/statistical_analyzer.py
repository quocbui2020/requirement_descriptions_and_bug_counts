import pandas as pd
import numpy as np #numpy-1.24.3 (Aim for data manipulation and numerical operations)
import seaborn as sns #seaborn-0.13.2 (Aim for data visualization)
import matplotlib.pyplot as plt #matplotlib-3.9.0
import statsmodels.api as sm 
from sklearn.decomposition import PCA
from sklearn.model_selection import train_test_split, GridSearchCV #scikit-learn-1.5.0
from sklearn.linear_model import LinearRegression, Ridge, LogisticRegression
from sklearn.metrics import mean_squared_error, r2_score, roc_curve, auc, roc_auc_score
import statsmodels.formula.api as smf
from statsmodels.stats.anova import anova_lm

class StatisticalAnalysisHelper:
    """
    A class to perform statistical analysis on a dataset.
    """
    @staticmethod
    def data_overview(data):
        """
        Provides basic information about the dataset.

        :param data: The dataset as a Pandas DataFrame.
        """
        print("Dataset Info:")
        print(data.info())
        print("\nSummary Statistics:")
        print(data.describe(include='all'))

    @staticmethod
    def clean_categorical_column_v1(data, column_name, missing_values=None, rare_categories=None, category_order=None, encoding='ordinal'):
        """
        Cleans a categorical column by handling missing values, grouping rare categories, and encoding.

        :param data: The dataset as a Pandas DataFrame.
        :param column_name: The name of the column to clean.
        :param missing_values: List of values to treat as missing (e.g., ['--', 'N/A']).
        :param rare_categories: List of categories to group into 'Other' (optional).
        :param category_order: The order of categories for ordinal encoding (e.g., ['P1', 'P2', 'P3', 'P4', 'P5']).
        :param encoding: Encoding method: 'ordinal' (default) or 'one-hot'.
        :return: The modified DataFrame.
        """
        # Handle missing values
        if missing_values:
            data[column_name] = data[column_name].replace(missing_values, np.nan)

        # Group rare categories (if provided)
        if rare_categories:
            data[column_name] = data[column_name].apply(
                lambda x: 'Other' if x in rare_categories else x
            )

        # Encode the column
        if encoding == 'ordinal':
            if category_order:
                # Use the specified order for ordinal encoding
                data[column_name] = pd.Categorical(data[column_name], categories=category_order, ordered=True)
                data[column_name] = data[column_name].cat.codes  # Convert to integer codes
            else:
                raise ValueError("For ordinal encoding, 'category_order' must be provided.")
        elif encoding == 'one-hot':
            # Use one-hot encoding
            data = pd.get_dummies(data, columns=[column_name], prefix=column_name)
        else:
            raise ValueError("Invalid encoding type. Use 'ordinal' or 'one-hot'.")

        return data

    # https://chatgpt.com/c/68cb6023-9df8-8329-90b3-fc5f884c7ec9
    @staticmethod
    def clean_categorical_column(data, column_name, missing_values=None, rare_categories=None, 
                                 category_order=None, encoding='ordinal', for_ANCOVA=False):
        """
        Cleans a categorical column for analysis, including missing values, rare categories, and encoding.

        :param data: Pandas DataFrame.
        :param column_name: Name of the column to clean.
        :param missing_values: List of values to treat as missing (e.g., ['--', 'N/A']).
        :param rare_categories: List of categories to group into 'Other' (optional).
        :param category_order: The order of categories (used for ordinal encoding or plotting).
        :param encoding: 'ordinal' (default) or 'one-hot'.
        :param for_ANCOVA: If True, keep as categorical factor (do not convert to numeric codes).
        :return: Modified DataFrame.
        """
        # Handle missing values
        if missing_values:
            data[column_name] = data[column_name].replace(missing_values, np.nan)

        # Group rare categories
        if rare_categories:
            data[column_name] = data[column_name].apply(lambda x: 'Other' if x in rare_categories else x)

        # Encoding
        if for_ANCOVA:
            # Keep as categorical factor for ANCOVA
            if category_order:
                data[column_name] = pd.Categorical(data[column_name], categories=category_order, ordered=False)
            else:
                data[column_name] = pd.Categorical(data[column_name])
        else:
            if encoding == 'ordinal':
                if category_order:
                    # Convert to ordered integer codes
                    data[column_name] = pd.Categorical(data[column_name], categories=category_order, ordered=True)
                    data[column_name] = data[column_name].cat.codes
                else:
                    raise ValueError("For ordinal encoding, 'category_order' must be provided.")
            elif encoding == 'one-hot':
                data = pd.get_dummies(data, columns=[column_name], prefix=column_name)
            else:
                raise ValueError("Invalid encoding type. Use 'ordinal' or 'one-hot'.")

        return data

    @staticmethod
    def calculate_correlation_analysis(data, column_list, print_result=False, correlation_threshold=0.0):
        # Get the subset of the DataFrame with the specified columns        
        if column_list is None:
            df_subset = data
        else:
            df_subset = data[column_list]
        
        # Calculate the correlation matrix
        correlation_matrix = df_subset.corr()
        
        # Drop highly correlated features with correlation > {correlation_threshold} if specified
        if correlation_threshold > 0.0:
            # Get upper triangle of correlation matrix
            upper = correlation_matrix.where(
                np.triu(np.ones(correlation_matrix.shape), k=1).astype(bool)
            )

            # Find features with correlation > {correlation_threshold}
            to_drop = [column for column in upper.columns if any(upper[column].abs() > correlation_threshold)]

            # Drop highly correlated features
            df_reduced = df_subset.drop(columns=to_drop)
            correlation_matrix = df_reduced.corr()

        # Print the correlation matrix
        print("Correlation Matrix:")
        print(correlation_matrix)
        
        if print_result:
            # Visualize the correlation matrix
            plt.figure(figsize=(12, 10))
            sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm', vmin=-1, vmax=1)
            plt.title('Correlation Matrix')
            plt.show()
        
        return correlation_matrix
    
    @staticmethod
    def perform_multiple_linear_regression_full_data(df, dependent_var, independent_vars, output_file=None):
        # Ensure numeric data
        df[independent_vars] = df[independent_vars].apply(pd.to_numeric, errors='coerce')
        df[dependent_var] = pd.to_numeric(df[dependent_var], errors='coerce')
        
        # Drop rows with missing values
        df = df.dropna(subset=independent_vars + [dependent_var])
        
        # Prepare the data for regression
        X = df[independent_vars]
        y = df[dependent_var]
        
        # Add a constant term (intercept)
        X = sm.add_constant(X)
        
        # Fit the model using statsmodels to get the summary statistics
        model_stats = sm.OLS(y, X).fit()
        
        # Print the summary statistics
        print(model_stats.summary())
        
        # Calculate predictions
        y_pred = model_stats.predict(X)
        
        # Calculate performance metrics
        mse = mean_squared_error(y, y_pred)
        r_squared = r2_score(y, y_pred)
        
        print(f'Mean Squared Error: {mse}')
        print(f'R-squared: {r_squared}')
        
        if output_file:
            # Save the model summary to a file
            with open(output_file, 'w') as f:
                f.write(model_stats.summary().as_text())
                f.write(f'Mean Squared Error: {mse}\n')
                f.write(f'R-squared: {r_squared}\n')

        return model_stats
    
    @staticmethod
    def perform_poisson_regression(df, dependent_var, independent_vars, output_file=None):
        """
        Performs Poisson regression for count data.

        :param df: The dataset as a Pandas DataFrame.
        :param dependent_var: The name of the dependent (count) variable.
        :param independent_vars: List of independent variable names.
        :param output_file: Optional file path to save the model summary.
        :return: The fitted Poisson regression model.
        """
        # Ensure numeric data
        df[independent_vars] = df[independent_vars].apply(pd.to_numeric, errors='coerce')
        df[dependent_var] = pd.to_numeric(df[dependent_var], errors='coerce')

        # Drop rows with missing values
        df = df.dropna(subset=independent_vars + [dependent_var])

        # Prepare the data for regression
        X = df[independent_vars]
        y = df[dependent_var]

        # Add a constant term (intercept)
        X = sm.add_constant(X)

        # Fit the Poisson regression model
        poisson_model = sm.GLM(y, X, family=sm.families.Poisson()).fit()

        # Print the summary statistics
        print(poisson_model.summary())

        if output_file:
            with open(output_file, 'w') as f:
                f.write(poisson_model.summary().as_text())

        return poisson_model
    
    @staticmethod
    def perform_ANCOVA(df, dependent_var, independent_vars, output_file=None):
        """
        Perform Analysis of Covariance (ANCOVA).

        :param df: The dataset as a Pandas DataFrame.
        :param dependent_var: The name of the dependent variable.
        :param independent_vars: List of independent variable names.
        :param output_file: Optional file path to save the model summary.
        :return: The fitted ANCOVA model.
        """
        # Ensure numeric data
        df[independent_vars] = df[independent_vars].apply(pd.to_numeric, errors='coerce')
        df[dependent_var] = pd.to_numeric(df[dependent_var], errors='coerce')

        # Drop rows with missing values
        df = df.dropna(subset=independent_vars + [dependent_var])

        # Prepare the data for ANCOVA
        model = sm.OLS(df[dependent_var], sm.add_constant(df[independent_vars])).fit()

        # Print the summary statistics
        print(model.summary())

        if output_file:
            with open(output_file, 'w') as f:
                f.write(model.summary().as_text())

        return model


    # Source: https://chatgpt.com/c/68cb6023-9df8-8329-90b3-fc5f884c7ec9
    @staticmethod
    def perform_ANCOVA2(df, dependent_var, covariates=None, factors=None, output_file=None):
        """
        Perform Analysis of Covariance (ANCOVA) using statsmodels.

        :param df: Pandas DataFrame containing the dataset.
        :param dependent_var: Name of the dependent variable (DV).
        :param covariates: List of continuous predictor variable names.
        :param factors: List of categorical predictor variable names.
        :param output_file: Optional path to save the ANCOVA results.
        :return: (fitted model, ANOVA table)
        """
        if covariates is None:
            covariates = []
        if factors is None:
            factors = []

        # Ensure DV is numeric
        df[dependent_var] = pd.to_numeric(df[dependent_var], errors="coerce")

        # Convert factors to categorical
        for f in factors:
            df[f] = df[f].astype("category")

        # Drop missing values
        df = df.dropna(subset=[dependent_var] + covariates + factors)

        # Build formula: DV ~ C(factor1) + C(factor2) + cov1 + cov2 ...
        terms = [f"C({f})" for f in factors] + covariates
        formula = f"{dependent_var} ~ " + " + ".join(terms)

        # Fit OLS model
        model = smf.ols(formula=formula, data=df).fit()

        # Run ANCOVA (Type II sums of squares is standard)
        anova_table = anova_lm(model, typ=2)

        # Print results
        print("=== ANCOVA Model Summary ===")
        print(model.summary())
        print("\n=== ANCOVA Table (Type II) ===")
        print(anova_table)

        # Save to file if requested
        if output_file:
            with open(output_file, "w") as f:
                f.write("=== ANCOVA Model Summary ===\n")
                f.write(model.summary().as_text())
                f.write("\n\n=== ANCOVA Table (Type II) ===\n")
                f.write(anova_table.to_string())

        return model, anova_table