import numpy as np
from sklearn.base import BaseEstimator
from sklearn.base import ClassifierMixin
from sklearn.externals.joblib import delayed, Parallel
from sklearn.linear_model.base import LinearClassifierMixin
from sklearn.utils import check_X_y
from sklearn.utils import check_random_state
from sklearn.metrics import log_loss

def softmax(X, w, n_labels=1):
    logits = np.dot(X, w[:-1]) + w[-1]
    if n_labels == 1:
        return 1./ (1. + np.exp(-logits))
    else:
        logits -= np.expand_dims(np.max(logits, axis=1), axis=1)
        logits = np.exp(logits)
        logits /= np.expand_dims(np.sum(logits), axis=1)
        return logits

def _log_loss(seed, mean, cov, X, y, labels, alpha):
    rng = check_random_state(seed)
    sample = rng.multivariate_normal(mean, cov)
    penalty = np.dot(sample, sample)
    n_labels = len(labels)
    if n_labels == 2:
        n_labels = 1
    sample = np.reshape(sample, (n_labels, -1))
    probs = softmax(X, sample.T, n_labels)
    weight = -log_loss(y, probs, labels=labels) - alpha*penalty
    return sample, weight

def softmax_1D(vec):
    vec = vec - np.max(vec)
    xform = np.exp(vec)
    xform /= np.sum(xform)
    return xform

class LogisticRegression(LinearClassifierMixin, BaseEstimator):
    """
    Logistic Regression using Sequential Monte Carlo.
    """
    def __init__(self, scale=1.0, n_iter=20000, random_state=None,
                 prior_scale=10.0, n_jobs=1, fit_intercept=True,
                 alpha=0.0):
        self.scale = scale
        self.n_iter = n_iter
        self.random_state = random_state
        self.prior_scale = prior_scale
        self.n_jobs = n_jobs
        self.fit_intercept = fit_intercept
        self.alpha = alpha

    def partial_fit(self, X=None, y=None, labels=None, n_features=None):
        # Called first time
        if X is None:
            if labels is None:
                raise ValueError("labels should be provided at first call to "
                                 "partial_fit.")
            if n_features is None:
                raise ValueError("n_features should be provided at first call "
                                 "to partial_fit.")

            self.classes_ = labels
            if self.fit_intercept:
                n_features += 1
            self.rng_ = check_random_state(self.random_state)

            n_labels = len(self.classes_)
            if len(self.classes_) == 2:
                n_labels = 1

            total = n_features * n_labels
            self.w_ = self.rng_.multivariate_normal(
                np.zeros(total),
                self.prior_scale*np.eye(total), size=self.n_iter)
        else:
            n_labels = len(self.classes_)
            if n_labels == 2:
                n_labels = 1
            X, y = check_X_y(X, y)

            if self.fit_intercept:
                n_features = X.shape[1] + 1
            else:
                n_features = X.shape[1]
            cov = self.scale * np.eye(self.w_.shape[-1])
            seeds = self.rng_.randint(2**32, size=self.n_iter)

            jobs = (
                delayed(_log_loss)(seed, w, cov, X, y, self.classes_, self.alpha)
                for seed, w in zip(seeds, self.w_)
            )
            results = np.array(Parallel(n_jobs=self.n_jobs)(jobs))
            samples = np.array([r[0] for r in results])
            weights = np.array([r[1] for r in results])
            self.samples_ = samples
            self.weights_ = softmax_1D(weights)

            counts = self.rng_.multinomial(self.n_iter,self.weights_)
            w = samples[np.repeat(np.arange(self.n_iter), counts)]
            coefs = np.mean(w, axis=0)
            self.coef_ = coefs[:, :n_features-1]
            self.intercept_ = coefs[:, -1]
            self.w_ = np.reshape(w, (self.n_iter, n_labels*n_features))

    def fit(self, X, y):
        self.partial_fit(labels=np.unique(y), n_features=X.shape[1])
        self.partial_fit(X, y)
        return self
