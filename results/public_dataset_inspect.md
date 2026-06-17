# Public Dataset Inspection

Stage 1 inspection only. This file records dataset schemas and suitability notes; it does not store raw datasets.

## Omni-MATH-Rule

- dataset_name: `Omni-MATH-Rule`
- loaded: False
- failure_reason: DatasetNotFoundError("Dataset 'Omni-MATH-Rule' doesn't exist on the Hub or cannot be accessed.")
- available_splits: []
- column_names: []
- problem/question field candidates: []
- answer/final_answer field candidates: []
- solution field candidates: []
- subject/domain/category/problem_type field candidates: []
- difficulty field candidates: []
- can_filter_number_theory: False
- contains_proof_like: False
- contains_image_multimodal_like: False
- contains_open_ended_like: False
- suitable_for_formal_eval: False
- suitable_for_training: False
- recommended_use: formal_eval

### First 2 Samples

```json
[]
```

## Omni-MATH

- dataset_name: `KbsdJames/Omni-MATH`
- loaded: True
- failure_reason: 
- available_splits: ['test']
- column_names: ['domain', 'difficulty', 'problem', 'solution', 'answer', 'source']
- problem/question field candidates: ['problem']
- answer/final_answer field candidates: ['answer']
- solution field candidates: ['solution']
- subject/domain/category/problem_type field candidates: ['domain']
- difficulty field candidates: ['difficulty']
- can_filter_number_theory: False
- contains_proof_like: False
- contains_image_multimodal_like: False
- contains_open_ended_like: False
- suitable_for_formal_eval: True
- suitable_for_training: False
- recommended_use: formal_eval

### First 2 Samples

```json
[
  {
    "domain": [
      "Mathematics -> Algebra -> Other"
    ],
    "difficulty": 8.0,
    "problem": "Let $ n(\\ge2) $ be a positive integer. Find the minimum $ m $, so that there exists $x_{ij}(1\\le i ,j\\le n)$ satisfying:\n(1)For every $1\\le i ,j\\le n, x_{ij}=max\\{x_{i1},x_{i2},...,x_{ij}\\} $ or $ x_{ij}=max\\{x_{1j},x_{2j},...,x_{ij}\\}.$\n(2)For every $1\\le i \\le n$, there are at most $m$ indices $k$ with $x_{ik}=max\\{x_{i1},x_{i2},...,x_{ik}\\}.$\n(3)For every $1\\le j \\le n$, there are at most $m$ indices $k$ with $x_{kj}=max\\{x_{1j},x_{2j},...,x_{kj}\\}.$",
    "solution": "\nLet \\( n (\\geq 2) \\) be a positive integer. We aim to find the minimum \\( m \\) such that there exists \\( x_{ij} \\) (for \\( 1 \\leq i, j \\leq n \\)) satisfying the following conditions:\n1. For every \\( 1 \\leq i, j \\leq n \\), \\( x_{ij} = \\max \\{ x_{i1}, x_{i2}, \\ldots, x_{ij} \\} \\) or \\( x_{ij} = \\max \\{ x_{1j}, x_{2j}, \\ldots, x_{ij} \\} \\).\n2. For every \\( 1 \\leq i \\leq n \\), there are at most \\( m \\) indices \\( k \\) such that \\( x_{ik} = \\max \\{ x_{i1}, x_{i2}, \\ldots, x_{ik} \\} \\).\n3. For every \\( 1 \\leq j \\leq n \\), there are at most \\( m \\) indices \\( k \\) such that \\( x_{kj} = \\max \\{ x_{1j}, x_{2j}, \\ldots, x_{kj} \\} \\).\n\nTo solve this, we need to consider the structure and constraints given by the problem. The solution involves ensuring that the maximum number of indices \\( k \\) for which \\( x_{ik} \\) or \\( x_{kj} \\) is the maximum is minimized.\n\nBy analyzing the constraints and constructing examples, it can be shown that the minimum \\( m \\) satisfying the conditions is:\n\\[\nm = 1 + \\left\\lceil \\frac{n}{2} \\right\\rceil.\n\\]\n\nThus, the minimum value of \\( m \\) is:\n\\[\n\\boxed{1 + \\left\\lceil \\frac{n}{2} \\right\\rceil}.\n\\]",
    "answer": "1 + \\left\\lceil \\frac{n}{2} \\right\\rceil",
    "source": "china_team_selection_test"
  },
  {
    "domain": [
      "Mathematics -> Geometry -> Plane Geometry -> Triangulations"
    ],
    "difficulty": 7.0,
    "problem": "In an acute scalene triangle $ABC$, points $D,E,F$ lie on sides $BC, CA, AB$, respectively, such that $AD \\perp BC, BE \\perp CA, CF \\perp AB$. Altitudes $AD, BE, CF$ meet at orthocenter $H$. Points $P$ and $Q$ lie on segment $EF$ such that $AP \\perp EF$ and $HQ \\perp EF$. Lines $DP$ and $QH$ intersect at point $R$. Compute $HQ/HR$.",
    "solution": "\nIn an acute scalene triangle \\(ABC\\), points \\(D, E, F\\) lie on sides \\(BC, CA, AB\\), respectively, such that \\(AD \\perp BC\\), \\(BE \\perp CA\\), \\(CF \\perp AB\\). Altitudes \\(AD, BE, CF\\) meet at orthocenter \\(H\\). Points \\(P\\) and \\(Q\\) lie on segment \\(EF\\) such that \\(AP \\perp EF\\) and \\(HQ \\perp EF\\). Lines \\(DP\\) and \\(QH\\) intersect at point \\(R\\). We aim to compute \\(\\frac{HQ}{HR}\\).\n\nNote that \\(H\\) and \\(A\\) are the incenter and \\(D\\)-excenter of \\(\\triangle DEF\\), respectively. Thus, \\(HQ\\) is an inradius of \\(\\triangle DEF\\). Let \\(R'\\) be the reflection of \\(Q\\) over \\(H\\). The homothety centered at \\(D\\) that maps the incircle to the \\(D\\)-excircle also maps \\(R'\\) to \\(P\\), implying that \\(D\\), \\(R'\\), and \\(P\\) are collinear, so \\(R' = R\\).\n\nTherefore, \\(\\frac{HQ}{HR} = 1\\).\n\nThe answer is \\(\\boxed{1}\\).",
    "answer": "1",
    "source": "usa_team_selection_test"
  }
]
```

## AI-MO/NuminaMath-1.5

- dataset_name: `AI-MO/NuminaMath-1.5`
- loaded: True
- failure_reason: 
- available_splits: ['train']
- column_names: ['problem', 'solution', 'answer', 'problem_type', 'question_type', 'problem_is_valid', 'solution_is_valid', 'source', 'synthetic']
- problem/question field candidates: ['problem', 'problem_is_valid', 'problem_type', 'question_type']
- answer/final_answer field candidates: ['answer']
- solution field candidates: ['solution', 'solution_is_valid']
- subject/domain/category/problem_type field candidates: ['problem_type', 'question_type']
- difficulty field candidates: []
- can_filter_number_theory: True
- contains_proof_like: True
- contains_image_multimodal_like: False
- contains_open_ended_like: False
- suitable_for_formal_eval: False
- suitable_for_training: True
- recommended_use: train_sft

### First 2 Samples

```json
[
  {
    "problem": "\nProblem 1. Find all prime numbers $p$ for which there exist positive integers $x, y$ and $z$ such that the number\n\n$$\nx^{p}+y^{p}+z^{p}-x-y-z\n$$\n\nis a product of exactly three distinct prime numbers.\n",
    "solution": "\nSolution. Let $A=x^{p}+y^{p}+z^{p}-x-y-z$. For $p=2$, we take $x=y=4$ and $z=3$. Then $A=30=2 \\cdot 3 \\cdot 5$. For $p=3$ we can take $x=3$ and $y=2$ and $z=1$. Then again $A=30=2 \\cdot 3 \\cdot 5$. For $p=5$ we can take $x=2$ and $y=1$ and $z=1$. Again $A=30=2 \\cdot 3 \\cdot 5$.\n\nAssume now that $p \\geqslant 7$. Working modulo 2 and modulo 3 we see that $A$ is divisible by both 2 and 3. Moreover, by Fermat's Little Theorem, we have\n\n$$\nx^{p}+y^{p}+z^{p}-x-y-z \\equiv x+y+z-x-y-z=0 \\bmod p \\text {. }\n$$\n\nTherefore, by the given condition, we have to solve the equation\n\n$$\nx^{p}+y^{p}+z^{p}-x-y-z=6 p\n$$\n\nIf one of the numbers $x, y$ and $z$ is bigger than or equal to 2 , let's say $x \\geqslant 2$, then\n\n$$\n6 p \\geqslant x^{p}-x=x\\left(x^{p-1}-1\\right) \\geqslant 2\\left(2^{p-1}-1\\right)=2^{p}-2\n$$\n\nIt is easy to check by induction that $2^{n}-2>6 n$ for all natural numbers $n \\geqslant 6$. This contradiction shows that there are no more values of $p$ which satisfy the required property.\n\nRemark. There are a couple of other ways to prove that $2^{p}-2>6 p$ for $p \\geqslant 7$. For example, we can use the Binomial Theorem as follows:\n\n$$\n2^{p}-2 \\geqslant 1+p+\\frac{p(p-1)}{2}+\\frac{p(p-1)(p-2)}{6}-2 \\geqslant 1+p+3 p+5 p-2>6 p\n$$\n\nWe can also use Bernoulli's Inequality as follows:\n\n$$\n2^{p}-2=8(1+1)^{p-3}-2 \\geqslant 8(1+(p-3))-2=8 p-18>6 p\n$$\n\nThe last inequality is true for $p \\geqslant 11$. For $p=7$ we can see directly that $2^{p}-2>6 p$.\n\nOne can also use calculus to show that $f(x)=2^{x}-6 x$ is increasing for $x \\geqslant 5$.\n",
    "answer": "proof",
    "problem_type": "Number Theory",
    "question_type": "math-word-problem",
    "problem_is_valid": "Yes",
    "solution_is_valid": "Yes",
    "source": "olympiads",
    "synthetic": false
  },
  {
    "problem": "\nProblem 2. Let $a, b$ be two distinct real numbers and let $c$ be a positive real number such that\n\n$$\na^{4}-2019 a=b^{4}-2019 b=c .\n$$\n\nProve that $-\\sqrt{c}<a b<0$.\n",
    "solution": "\nSolution. Firstly, we see that\n\n$$\n2019(a-b)=a^{4}-b^{4}=(a-b)(a+b)\\left(a^{2}+b^{2}\\right)\n$$\n\nSince $a \\neq b$, we get $(a+b)\\left(a^{2}+b^{2}\\right)=2019$, so $a+b \\neq 0$. Thus\n\n$$\n\\begin{aligned}\n2 c & =a^{4}-2019 a+b^{4}-2019 b \\\\\n& =a^{4}+b^{4}-2019(a+b) \\\\\n& =a^{4}+b^{4}-(a+b)^{2}\\left(a^{2}+b^{2}\\right) \\\\\n& =-2 a b\\left(a^{2}+a b+b^{2}\\right)\n\\end{aligned}\n$$\n\nHence $a b\\left(a^{2}+a b+b^{2}\\right)=-c0\n$$\n\nthus $a b-a b$ (the equality does not occur since $a+b \\neq 0$ ). So\n\n$$\n-c=a b\\left(a^{2}+a b+b^{2}\\right)<-(a b)^{2} \\Longrightarrow(a b)^{2}<c \\Rightarrow-\\sqrt{c}<a b<\\sqrt{c}\n$$\n\nTherefore, we have $-\\sqrt{c}<a b<0$.\n\nRemark. We can get $c=-a b\\left(a^{2}+a b+b^{2}\\right)$ in several other ways. For example using that,\n\n$$\n(a-b) c=a\\left(b^{4}-2019 b\\right)-b\\left(a^{4}-2019 a\\right)=a b\\left(b^{3}-a^{3}\\right)=a b(b-a)\\left(a^{2}+a b+b^{2}\\right)\n$$\n\nWe can also divide $f(x)=x^{4}-2019 x-c$ by $(x-a)(x-b)$ and look at the constant term of the remainder.\n",
    "answer": "proof",
    "problem_type": "Algebra",
    "question_type": "proof",
    "problem_is_valid": "Yes",
    "solution_is_valid": "Incomplete",
    "source": "olympiads",
    "synthetic": false
  }
]
```

## AI-MO/NuminaMath-CoT

- dataset_name: `AI-MO/NuminaMath-CoT`
- loaded: True
- failure_reason: 
- available_splits: ['train', 'test']
- column_names: ['source', 'problem', 'solution', 'messages']
- problem/question field candidates: ['problem']
- answer/final_answer field candidates: []
- solution field candidates: ['messages', 'solution']
- subject/domain/category/problem_type field candidates: []
- difficulty field candidates: []
- can_filter_number_theory: False
- contains_proof_like: False
- contains_image_multimodal_like: False
- contains_open_ended_like: False
- suitable_for_formal_eval: False
- suitable_for_training: True
- recommended_use: backup

### First 2 Samples

```json
[
  {
    "source": "synthetic_math",
    "problem": "Consider the terms of an arithmetic sequence: $-\\frac{1}{3}, y+2, 4y, \\ldots$. Solve for $y$.",
    "solution": "For an arithmetic sequence, the difference between consecutive terms must be equal. Therefore, we can set up the following equations based on the sequence given:\n\\[ (y + 2) - \\left(-\\frac{1}{3}\\right) = 4y - (y+2) \\]\n\nSimplify and solve these equations:\n\\[ y + 2 + \\frac{1}{3} = 4y - y - 2 \\]\n\\[ y + \\frac{7}{3} = 3y - 2 \\]\n\\[ \\frac{7}{3} + 2 = 3y - y \\]\n\\[ \\frac{13}{3} = 2y \\]\n\\[ y = \\frac{13}{6} \\]\n\nThus, the value of $y$ that satisfies the given arithmetic sequence is $\\boxed{\\frac{13}{6}}$.",
    "messages": [
      {
        "content": "Consider the terms of an arithmetic sequence: $-\\frac{1}{3}, y+2, 4y, \\ldots$. Solve for $y$.",
        "role": "user"
      },
      {
        "content": "For an arithmetic sequence, the difference between consecutive terms must be equal. Therefore, we can set up the following equations based on the sequence given:\n\\[ (y + 2) - \\left(-\\frac{1}{3}\\right) = 4y - (y+2) \\]\n\nSimplify and solve these equations:\n\\[ y + 2 + \\frac{1}{3} = 4y - y - 2 \\]\n\\[ y + \\frac{7}{3} = 3y - 2 \\]\n\\[ \\frac{7}{3} + 2 = 3y - y \\]\n\\[ \\frac{13}{3} = 2y \\]\n\\[ y = \\frac{13}{6} \\]\n\nThus, the value of $y$ that satisfies the given arithmetic sequence is $\\boxed{\\frac{13}{6}}$.",
        "role": "assistant"
      }
    ]
  },
  {
    "source": "synthetic_math",
    "problem": "Suppose that $g(x) = 5x - 3$. What is $g^{-1}(g^{-1}(14))$?",
    "solution": "First, we need to find the inverse function $g^{-1}(x)$. Given $g(x) = 5x - 3$, solve for $x$:\n\\[ y = 5x - 3 \\]\n\\[ y + 3 = 5x \\]\n\\[ x = \\frac{y + 3}{5} \\]\nThus, $g^{-1}(x) = \\frac{x + 3}{5}$.\n\nNow, apply $g^{-1}$ twice to the given value $14$:\n\\[ g^{-1}(14) = \\frac{14 + 3}{5} = \\frac{17}{5} \\]\n\\[ g^{-1}\\left(\\frac{17}{5}\\right) = \\frac{\\frac{17}{5} + 3}{5} = \\frac{\\frac{17}{5} + \\frac{15}{5}}{5} = \\frac{32}{5 \\times 5} = \\frac{32}{25} \\]\n\nThus, $g^{-1}(g^{-1}(14)) = \\boxed{\\frac{32}{25}}$.",
    "messages": [
      {
        "content": "Suppose that $g(x) = 5x - 3$. What is $g^{-1}(g^{-1}(14))$?",
        "role": "user"
      },
      {
        "content": "First, we need to find the inverse function $g^{-1}(x)$. Given $g(x) = 5x - 3$, solve for $x$:\n\\[ y = 5x - 3 \\]\n\\[ y + 3 = 5x \\]\n\\[ x = \\frac{y + 3}{5} \\]\nThus, $g^{-1}(x) = \\frac{x + 3}{5}$.\n\nNow, apply $g^{-1}$ twice to the given value $14$:\n\\[ g^{-1}(14) = \\frac{14 + 3}{5} = \\frac{17}{5} \\]\n\\[ g^{-1}\\left(\\frac{17}{5}\\right) = \\frac{\\frac{17}{5} + 3}{5} = \\frac{\\frac{17}{5} + \\frac{15}{5}}{5} = \\frac{32}{5 \\times 5} = \\frac{32}{25} \\]\n\nThus, $g^{-1}(g^{-1}(14)) = \\boxed{\\frac{32}{25}}$.",
        "role": "assistant"
      }
    ]
  }
]
```
