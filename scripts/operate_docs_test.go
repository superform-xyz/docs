package rule_test

import (
	"encoding/json"
	"math/big"
	"os"
	"strings"
	"testing"

	"github.com/superform-xyz/superman-strategy/internal/domain"
	"github.com/superform-xyz/superman-strategy/internal/rule"
	"github.com/superform-xyz/superman-strategy/internal/sim"
)

type docsSnippet struct {
	Name string          `json:"name"`
	Kind string          `json:"kind"`
	Data json.RawMessage `json:"data"`
}
type docsCase struct {
	Name         string            `json:"name"`
	Rule         domain.RuleNode   `json:"rule"`
	Size         string            `json:"size"`
	Snapshot     map[string]string `json:"snapshot"`
	Want         bool              `json:"want"`
	Amount       string            `json:"amount"`
	RuntimeError bool              `json:"runtime_error"`
}
type docsInputs struct {
	Snippets []docsSnippet           `json:"snippets"`
	Cases    []docsCase              `json:"cases"`
	Live     []domain.StrategyConfig `json:"live"`
}

func docsLoad(t *testing.T) docsInputs {
	t.Helper()
	b, err := os.ReadFile(os.Getenv("OPERATE_DOCS_FIXTURE"))
	if err != nil {
		t.Fatal(err)
	}
	var in docsInputs
	if err = json.Unmarshal(b, &in); err != nil {
		t.Fatal(err)
	}
	return in
}
func TestOperateDocsSnippets(t *testing.T) {
	in := docsLoad(t)
	c := rule.NewCompiler()
	for _, s := range in.Snippets {
		t.Run(s.Name, func(t *testing.T) {
			switch s.Kind {
			case "rule":
				var n domain.RuleNode
				if err := json.Unmarshal(s.Data, &n); err != nil {
					t.Fatal(err)
				}
				if err := rule.NewStrategyValidator(c).Validate(&domain.StrategyConfig{Rules: n}); err != nil {
					t.Fatal(err)
				}
			case "numeric":
				var x string
				if err := json.Unmarshal(s.Data, &x); err != nil {
					t.Fatal(err)
				}
				if err := c.ValidateNumericExprStrict(x, rule.IdentPolicyForConfig(nil, nil)); err != nil {
					t.Fatal(err)
				}
			case "action":
				var a domain.ActionConfig
				if err := json.Unmarshal(s.Data, &a); err != nil {
					t.Fatal(err)
				}
				if err := a.Validate(); err != nil {
					t.Fatal(err)
				}
				if err := c.ValidateNumericExprStrict(a.SizeExpr, rule.IdentPolicyForConfig(nil, nil)); err != nil {
					t.Fatal(err)
				}
			case "params":
				var p map[string]any
				if err := json.Unmarshal(s.Data, &p); err != nil {
					t.Fatal(err)
				}
				if _, err := domain.DecodeActionPlan(p); err != nil {
					t.Fatal(err)
				}
			case "config":
				var cfg domain.StrategyConfig
				if err := json.Unmarshal(s.Data, &cfg); err != nil {
					t.Fatal(err)
				}
				if err := cfg.Validate(); err != nil {
					t.Fatal(err)
				}
				if err := rule.NewStrategyValidator(c).Validate(&cfg); err != nil {
					t.Fatal(err)
				}
			case "conviction":
				var cc domain.ConvictionConfig
				if err := json.Unmarshal(s.Data, &cc); err != nil {
					t.Fatal(err)
				}
				if err := cc.Validate(); err != nil {
					t.Fatal(err)
				}
			default:
				t.Fatalf("unvalidated snippet kind: %s", s.Kind)
			}
		})
	}
}
func TestOperateDocsEvaluator(t *testing.T) {
	in := docsLoad(t)
	for _, tc := range in.Cases {
		t.Run(tc.Name, func(t *testing.T) {
			c := rule.NewCompiler()
			ev := rule.NewEvaluator()
			cfg := domain.StrategyConfig{Rules: tc.Rule, ActionConfig: domain.ActionConfig{SizeExpr: tc.Size}}
			if err := rule.NewStrategyValidator(c).Validate(&cfg); err != nil {
				t.Fatal(err)
			}
			compiled, err := c.Compile(tc.Rule)
			if err != nil {
				t.Fatal(err)
			}
			snap := domain.EvalSnapshot{}
			for k, v := range tc.Snapshot {
				n, _, err := big.ParseFloat(v, 10, 256, big.ToNearestEven)
				if err != nil {
					t.Fatal(err)
				}
				snap[k] = n
			}
			got, err := ev.Eval(compiled, snap)
			if tc.RuntimeError {
				if err == nil {
					t.Fatal("expected runtime error")
				}
				t.Log(err)
				return
			}
			if err != nil {
				t.Fatal(err)
			}
			if got != tc.Want {
				t.Fatalf("rule=%v want %v", got, tc.Want)
			}
			if got && tc.Size != "" {
				p, err := c.CompileNumeric(tc.Size)
				if err != nil {
					t.Fatal(err)
				}
				n, err := ev.EvalNumber(p, snap)
				if err != nil {
					t.Fatal(err)
				}
				amount, _ := n.Int(nil)
				if amount.String() != tc.Amount {
					t.Fatalf("size=%s want=%s", amount.String(), tc.Amount)
				}
				t.Logf("fired=%v truncated_size=%s", got, amount)
			} else {
				t.Logf("fired=%v", got)
			}
		})
	}
}
func TestOperateDocsCapturedConfigsAndSimulation(t *testing.T) {
	in := docsLoad(t)
	for _, cfg := range in.Live {
		t.Run(cfg.ID, func(t *testing.T) {
			if err := cfg.Validate(); err != nil {
				t.Fatal(err)
			}
			if err := rule.NewStrategyValidator(rule.NewCompiler()).Validate(&cfg); err != nil {
				t.Fatal(err)
			}
			err := sim.ValidateStrategy(&cfg)
			liquidity := strings.Contains(cfg.ActionConfig.SizeExpr, "_liquidity")
			if liquidity {
				if err == nil || !strings.Contains(err.Error(), "liquidity observations are not supported by simulation replay") {
					t.Fatalf("wanted liquidity rejection, got %v", err)
				}
				t.Log(err)
			} else if err != nil {
				t.Fatal(err)
			}
		})
	}
}
func TestOperateDocsRejectedSyntax(t *testing.T) {
	c := rule.NewCompiler()
	for _, x := range []string{"min(1,2,3)", "floor(1.5)", "pow(10,6)", "true ? 10 : 20", "vault_pps_stale", "tick_age_seconds", "ys_0x91c056b6d4311a743614fbc03ac32d4e6a2d3a3c_alloc"} {
		if err := c.ValidateNumericExprStrict(x, rule.IdentPolicyForConfig(nil, nil)); err == nil {
			t.Fatalf("unexpectedly accepted %s", x)
		}
	}
	for _, raw := range []string{`{"type":"NOT","child":{"type":"EXPR","expr":"false"}}`, `{"type":"VOTE","threshold":2,"children":[{"type":"EXPR","expr":"true"},{"type":"EXPR","expr":"false"}]}`} {
		var n domain.RuleNode
		json.Unmarshal([]byte(raw), &n)
		if err := c.ValidateRule(n); err == nil {
			t.Fatalf("unexpectedly accepted %s", raw)
		}
	}
}
