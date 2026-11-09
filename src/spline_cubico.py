"""
spline_cubico.py
================
Implementación propia (desde cero, sin librerías de interpolación) del
Spline Cúbico Natural, en su forma explícita y en su forma paramétrica.

Spline explícito (un tramo por intervalo [x_i, x_{i+1}]):
    S_i(x) = a_i + b_i (x - x_i) + c_i (x - x_i)^2 + d_i (x - x_i)^3

Spline paramétrico (dos splines explícitos que comparten el parámetro t):
    X_i(t) = a_xi + b_xi (t - t_i) + c_xi (t - t_i)^2 + d_xi (t - t_i)^3
    Y_i(t) = a_yi + b_yi (t - t_i) + c_yi (t - t_i)^2 + d_yi (t - t_i)^3

Condiciones impuestas (n+1 nodos -> n tramos -> 4n incógnitas):
    * Interpolación:   S_i(x_i) = y_i,  S_i(x_{i+1}) = y_{i+1}       (C0)
    * Derivada 1 igual en nodos interiores: S_i'(x_{i+1}) = S_{i+1}'(x_{i+1}) (C1)
    * Derivada 2 igual en nodos interiores: S_i''(x_{i+1}) = S_{i+1}''(x_{i+1}) (C2)
    * Frontera natural: S''(x_0) = S''(x_n) = 0
Estas condiciones se reducen a un sistema TRIDIAGONAL en los c_i que se
resuelve con el algoritmo de Thomas.
"""
from __future__ import annotations

import numpy as np


# ---------------------------------------------------------------------------
# Algoritmo de Thomas para sistemas tridiagonales
# ---------------------------------------------------------------------------
def resolver_tridiagonal(sub, diag, sup, rhs):
    """Resuelve A z = rhs con A tridiagonal (sub-, diagonal y super-diagonal)."""
    n = len(diag)
    cp = np.zeros(n)
    dp = np.zeros(n)
    cp[0] = sup[0] / diag[0] if n > 1 else 0.0
    dp[0] = rhs[0] / diag[0]
    for i in range(1, n):
        m = diag[i] - sub[i] * cp[i - 1]
        cp[i] = sup[i] / m if i < n - 1 else 0.0
        dp[i] = (rhs[i] - sub[i] * dp[i - 1]) / m
    z = np.zeros(n)
    z[-1] = dp[-1]
    for i in range(n - 2, -1, -1):
        z[i] = dp[i] - cp[i] * z[i + 1]
    return z


# ---------------------------------------------------------------------------
# Spline cúbico natural EXPLÍCITO  y = S(x)
# ---------------------------------------------------------------------------
class SplineCubicoNatural:
    """Spline cúbico natural explícito S(x) con x estrictamente creciente."""

    def __init__(self, x, y):
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        if np.any(np.diff(x) <= 0):
            raise ValueError("Las abscisas deben ser estrictamente crecientes "
                             "(x0 < x1 < ... < xn) para el spline explícito.")
        n = len(x) - 1                     # número de tramos
        h = np.diff(x)                     # h_i = x_{i+1} - x_i
        a = y.copy()                       # a_i = y_i

        # Sistema tridiagonal para c_0..c_n  (c_0 = c_n = 0 -> natural)
        sub = np.zeros(n + 1)
        diag = np.ones(n + 1)
        sup = np.zeros(n + 1)
        rhs = np.zeros(n + 1)
        for i in range(1, n):
            sub[i] = h[i - 1]
            diag[i] = 2.0 * (h[i - 1] + h[i])
            sup[i] = h[i]
            rhs[i] = 3.0 * ((a[i + 1] - a[i]) / h[i] - (a[i] - a[i - 1]) / h[i - 1])
        c = resolver_tridiagonal(sub, diag, sup, rhs)

        b = np.zeros(n)
        d = np.zeros(n)
        for i in range(n):
            b[i] = (a[i + 1] - a[i]) / h[i] - h[i] * (2.0 * c[i] + c[i + 1]) / 3.0
            d[i] = (c[i + 1] - c[i]) / (3.0 * h[i])

        self.x, self.h = x, h
        self.a, self.b, self.c, self.d = a[:-1], b, c[:-1], d
        self.n = n

    # -- evaluación ---------------------------------------------------------
    def _tramo(self, xv):
        i = np.searchsorted(self.x, xv, side="right") - 1
        return np.clip(i, 0, self.n - 1)

    def __call__(self, xv, derivada=0, tramo=None):
        xv = np.asarray(xv, dtype=float)
        i = self._tramo(xv) if tramo is None else np.full(xv.shape, tramo)
        dx = xv - self.x[i]
        a, b, c, d = self.a[i], self.b[i], self.c[i], self.d[i]
        if derivada == 0:
            return a + b * dx + c * dx**2 + d * dx**3
        if derivada == 1:
            return b + 2 * c * dx + 3 * d * dx**2
        if derivada == 2:
            return 2 * c + 6 * d * dx
        raise ValueError("derivada debe ser 0, 1 o 2")

    def coeficientes(self):
        """Tabla (i, x_i, x_{i+1}, a_i, b_i, c_i, d_i)."""
        return [(i, self.x[i], self.x[i + 1], self.a[i], self.b[i], self.c[i], self.d[i])
                for i in range(self.n)]

    def verificar_continuidad(self):
        """Máximo salto de S, S', S'' en los nodos interiores (C0, C1, C2)."""
        saltos = []
        for k in range(3):
            m = 0.0
            for i in range(self.n - 1):
                xi = self.x[i + 1]
                izq = self(np.array([xi]), k, tramo=i)[0]
                der = self(np.array([xi]), k, tramo=i + 1)[0]
                m = max(m, abs(izq - der))
            saltos.append(m)
        return saltos  # [C0, C1, C2]


# ---------------------------------------------------------------------------
# Spline cúbico natural PARAMÉTRICO  (X(t), Y(t))
# ---------------------------------------------------------------------------
class SplineParametrico:
    """Spline cúbico paramétrico con parametrización por longitud de cuerda:
        t_0 = 0,  t_{i+1} = t_i + || P_{i+1} - P_i ||
    """

    def __init__(self, puntos):
        P = np.asarray(puntos, dtype=float)
        cuerdas = np.hypot(np.diff(P[:, 0]), np.diff(P[:, 1]))
        t = np.concatenate([[0.0], np.cumsum(cuerdas)])
        self.P, self.t = P, t
        self.Sx = SplineCubicoNatural(t, P[:, 0])
        self.Sy = SplineCubicoNatural(t, P[:, 1])
        self.n = len(P) - 1

    def __call__(self, tv, derivada=0):
        return self.Sx(tv, derivada), self.Sy(tv, derivada)

    def curva(self, muestras_por_tramo=60):
        """Puntos densos de la curva completa (y el tramo al que pertenecen)."""
        T, idx = [], []
        for i in range(self.n):
            ts = np.linspace(self.t[i], self.t[i + 1], muestras_por_tramo,
                             endpoint=(i == self.n - 1))
            T.append(ts)
            idx.append(np.full(len(ts), i))
        T = np.concatenate(T)
        X, Y = self(T)
        return X, Y, np.concatenate(idx)

    def tramo(self, i, muestras=60):
        ts = np.linspace(self.t[i], self.t[i + 1], muestras)
        return self.Sx(ts, tramo=i), self.Sy(ts, tramo=i)

    def verificar_continuidad(self):
        sx = self.Sx.verificar_continuidad()
        sy = self.Sy.verificar_continuidad()
        return [max(a, b) for a, b in zip(sx, sy)]

    def coeficientes(self):
        cx = self.Sx.coeficientes()
        cy = self.Sy.coeficientes()
        return [(i, ti, ti1, ax, bx, cxx, dx, ay, by, cyy, dy)
                for (i, ti, ti1, ax, bx, cxx, dx), (_, _, _, ay, by, cyy, dy) in zip(cx, cy)]


def validar_con_scipy(spline: SplineParametrico):
    """Compara la implementación propia con scipy (si está disponible)."""
    try:
        from scipy.interpolate import CubicSpline
    except ImportError:  # pragma: no cover
        return None
    ts = np.linspace(spline.t[0], spline.t[-1], 2000)
    X, Y = spline(ts)
    cx = CubicSpline(spline.t, spline.P[:, 0], bc_type="natural")
    cy = CubicSpline(spline.t, spline.P[:, 1], bc_type="natural")
    return float(max(np.max(np.abs(X - cx(ts))), np.max(np.abs(Y - cy(ts)))))
