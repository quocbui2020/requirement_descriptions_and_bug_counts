import pandas as pd
import numpy as np #numpy-1.24.3 (Aim for data manipulation and numerical operations)
import seaborn as sns #seaborn-0.13.2 (Aim for data visualization)
import matplotlib.pyplot as plt #matplotlib-3.9.0
import statsmodels.api as sm 
from sklearn.decomposition import PCA
from sklearn.model_selection import train_test_split, GridSearchCV #scikit-learn-1.5.0
from sklearn.linear_model import LinearRegression, Ridge, LogisticRegression
from sklearn.metrics import mean_squared_error, r2_score, roc_curve, auc, roc_auc_score

class StatisticalAnalysisHelper:
    """
    A class to perform statistical analysis on a dataset.
    """

    def __init__(self, data):
        """
        Initializes the StatisticalAnalysisHelper with the provided data.

        :param data: The dataset to analyze.
        """
        self.data = data
    
    def calculate_correlation_analysis(self, columns, print_result=False, correlation_threshold=0.0):
        # Convert the data to a pandas DataFrame
        df = pd.DataFrame(self.data)
        
        if columns is None:
            df_subset = df
        else:
            df_subset = df[columns]
        
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
    
    def perform_multiple_linear_regression_full_data(self, dependent_var, independent_vars, output_file=None):
        # Convert the data to a pandas DataFrame
        df = pd.DataFrame(self.data)
        
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