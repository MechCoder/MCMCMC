import numpy as np
from sklearn.base import ClassifierMixin
from sklearn.linear_model.base import LinearClassifierMixin
from sklearn.utils import check_X_y
from sklearn.utils import check_random_state
from sklearn.metrics import log_loss

class LogisticRegression(LinearClassifierMixin):
    """
    Logistic Regression using Sequential Monte Carlo.
    """
    def __init__(self, scale=1.0, n_iter=20000, random_state=None, prior_scale=0.1):
        self.scale = scale
        self.n_iter = n_iter
        self.random_state = random_state
        self.prior_scale = prior_scale

    def logistic_function(self, X, w):
        lin = np.matmul(X,w[:-1])+w[-1]
        return 1./ (1. + np.exp(-lin))

    def softmax(self, vec):
        vec = vec - np.max(vec)
        xform = np.exp(vec)
        xform /= np.sum(xform)
        return xform

    def adjust_samples(self,weight_t,w_samples_t):
        resamped = self.rng.multinomial(self.n_iter,weight_t)
        coef = np.mean(np.repeat(w_samples_t, resamped, axis=0), axis=0)
        return coef

    def partial_fit(self, X, y):
        X, y = check_X_y(X, y)
        n_features = X.shape[1] + 1

        # Called first time
        if not hasattr(self, "time_"):
            self.rng_ = check_random_state(self.random_state)
            self.w_ = self.rng_.multivariate_normal(
                np.zeros(n_features),
                self.prior_scale * np.eye(n_features), size=self.n_iter)
            self.time_ = 1
        else:
            self.time_ += 1
            samples = np.zeros((self.n_iter, n_features))
            cov = self.scale * np.eye(n_features)
            weights = np.zeros(self.n_iter)

            for i in range(self.n_iter):
                samples[i] = self.rng_.multivariate_normal(self.w_[i], cov)
                weights[i] = -log_loss(y, self.logistic_function(X, samples[i]))
            self.weights_ = self.softmax(weights)
            self.w_ = samples[self.rng_.multinomial(self.n_iter, self.weights_)]


    def fit(self, X, y, t):
        self.rng = check_random_state(self.random_state)
        X, y = check_X_y(X, y)
        w_dim = X.shape[1] + 1

        unique_t, self.rev_index = np.unique(t, return_inverse=True)
        w_samples = np.ones((self.n_iter, len(unique_t), w_dim))
        weights = np.ones((self.n_iter, len(unique_t)))
        cov = self.scale * np.eye(w_dim)
        for i in range(self.n_iter):
            w = np.random.multivariate_normal(
                np.zeros(w_dim), np.eye(w_dim)*10)

            for j, time in enumerate(unique_t):
                t_ind = np.where(t==time)
                X_t = X[t_ind]
                y_t = y[t_ind]
                w = self.rng.multivariate_normal(w, cov)
                w_samples[i][j]=w
                weights[i][j] = -log_loss(y_t, self.logistic_function(X_t, w))

        self.weights_ = np.apply_along_axis(self.softmax, 0, weights)
        self.w_samples_ = w_samples

        coef = np.array([self.adjust_samples(self.weights_[:,i],self.w_samples_[:,i]) \
                        for i in xrange(self.weights_.shape[1])])
        self.coef_ = coef[:,:-1]
        self.intercept_ = coef[:,-1]

    def predict(self, X):
        return np.array(np.sum(np.multiply(self.coef_[self.rev_index],X),axis=1) +\
         self.intercept_[self.rev_index] > 0,dtype=np.int)